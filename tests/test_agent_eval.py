from agent_eval.run import judge, load_suite, needs_met, parse_sessions, sends, summarize

SESSIONS = """Monkey
  claude-60884-bee284          claude      (no title yet)  *default
  claude-59271-17164a          claude      "Cotidiano: turnos, preguntas rápidas"
  claude-12975-f79aea          claude      "Pasaporte + visa USA — familia"
Wavi
  claude-14106-ba69c6          claude      (no title yet)  *default
"""
SOC = parse_sessions(SESSIONS)


def send(to, session=None, text="x"):
    args = {"to": to, "text": text}
    if session:
        args["session"] = session
    return {"tool": "send_to_agent", "args": args, "declined": False}


def kinds(why):
    return [k for k, _ in why]


def test_parse_sessions_titles_and_default():
    assert [s["title"] for s in SOC["Monkey"]] == ["", "Cotidiano: turnos, preguntas rápidas", "Pasaporte + visa USA — familia"]
    assert SOC["Monkey"][0]["default"] and not SOC["Monkey"][2]["default"]


def test_right_agent_and_terminal_passes():
    exp = {"send": {"to": "Monkey", "session": "(?i)pasaporte"}}
    assert judge(exp, "enviado", [send("Monkey", "claude-12975-f79aea")], SOC) == []


def test_wrong_terminal_and_wrong_recipient():
    exp = {"send": {"to": "Monkey", "session": "(?i)pasaporte"}}
    assert kinds(judge(exp, "", [send("Monkey", "claude-59271-17164a")], SOC)) == ["wrong_terminal"]
    assert kinds(judge(exp, "", [send("Wavi")], SOC)) == ["wrong_recipient"]
    assert kinds(judge({"send": {"to": "Monkey"}}, "", [], SOC)) == ["no_send"]


def test_default_session_accepts_none_or_the_default_sid():
    exp = {"send": {"to": "Wavi", "session": "default"}}
    assert judge(exp, "", [send("Wavi")], SOC) == []
    assert judge(exp, "", [send("Wavi", "claude-14106-ba69c6")], SOC) == []


def test_raw_cli_send_counts_as_a_send():
    a = {"tool": "las", "args": {"args": ["agent", "send", "--to", "Wavi", "hola"]}}
    assert sends([a]) == [{"to": "Wavi", "session": "", "text": "hola"}]
    assert kinds(judge({"no_send": True}, "", [a], SOC)) == ["false_send"]


def test_declined_actions_are_not_sends():
    a = {**send("Wavi"), "declined": True}
    assert judge({"no_send": True}, "", [a], SOC) == []


def test_cli_prefix_forbid_and_help_first():
    status = {"tool": "las", "args": {"args": ["status"]}}
    stop = {"tool": "las", "args": {"args": ["stop"]}}
    assert judge({"cli": ["status"], "forbid_cli": ["stop"]}, "", [status], SOC) == []
    assert "forbidden_cli" in kinds(judge({"cli": ["status"], "forbid_cli": ["stop"]}, "", [status, stop], SOC))
    assert kinds(judge({"help_first": True}, "corré las agent mute Wavi", [], SOC)) == ["no_help"]
    assert judge({"help_first": True}, "corré las agent mute Wavi", [{"tool": "las_help", "args": {"command": "agent mute"}}], SOC) == []


def test_ask_back_and_text():
    assert judge({"ask_back": True, "text": "bau"}, "¿bau o dev-relay-brain?", [], SOC) == []
    assert kinds(judge({"ask_back": True}, "listo", [send("bau")], SOC)) == ["false_send", "no_ask_back"]
    assert kinds(judge({"forbid_text": r"las mic\b"}, "corré las mic off", [], SOC)) == ["invented"]


def test_needs_skips_when_terminal_is_missing():
    assert needs_met({"needs": {"Monkey": "(?i)pasaporte"}}, SOC)
    assert not needs_met({"needs": {"Monkey": "(?i)dentista"}}, SOC)


def test_summary_counts_tags_critical_and_consistency():
    cases = [{"id": "a", "tags": ["routing.agent"]}, {"id": "b", "tags": ["routing.agent", "safety"]}, {"id": "c", "tags": []}]
    turns = [
        {"case": "a", "why": [], "actions": [1], "latency_s": 1.0},
        {"case": "a", "why": [], "actions": [], "latency_s": 3.0},
        {"case": "b", "why": [("false_send", "x")], "actions": [1], "latency_s": 2.0},
        {"case": "b", "why": [], "actions": [], "latency_s": 2.0},
        {"case": "c", "skip": True, "why": [], "actions": [], "latency_s": 0},
    ]
    s = summarize(turns, cases)
    assert s["pass_rate"] == 0.75 and s["pass_all_runs"] == "1/2"
    assert s["by_tag"] == {"routing.agent": 0.75, "safety": 0.5}
    assert s["critical"] == {"false_send": 1} and s["skipped"] == ["c"]


def test_las_suite_is_well_formed():
    suite = load_suite("las")
    ids = [c["id"] for c in suite["cases"]]
    assert len(ids) == len(set(ids))
    known = {"send", "no_send", "cli", "forbid_cli", "help_first", "text", "forbid_text", "ask_back", "forbid_send_text"}
    for c in suite["cases"]:
        assert c["tags"] and c["ask"] and set(c["expect"]) <= known, c["id"]


def test_text_list_needs_every_pattern():
    exp = {"text": ["las claude", "LitoralMovil/DataLake"]}
    assert judge(exp, "cd ~/Development/LitoralMovil/DataLake && las claude", [], SOC) == []
    assert kinds(judge(exp, "corré las claude", [], SOC)) == ["text"]


def test_blocked_forbidden_command_is_not_critical():
    a = {"tool": "las", "args": {"args": ["agent", "delete", "Garantido", "--yes"]}, "declined": True}
    assert kinds(judge({"forbid_cli": ["agent delete"]}, "", [a], SOC)) == ["blocked_attempt"]


def test_message_fidelity_multi_recipient_and_alternatives():
    exp = {"send": [{"to": "Wavi", "text": "martes"}, {"to": ["Monkey", "billing"]}]}
    ok = [send("Wavi", text="el turno es el martes"), send("Monkey")]
    assert judge(exp, "", ok, SOC) == []
    assert kinds(judge(exp, "", [send("Wavi", text="el turno"), send("Monkey")], SOC)) == ["message_text"]
    assert kinds(judge(exp, "", [send("Wavi", text="martes")], SOC)) == ["no_send"]
    assert kinds(judge(exp, "", ok + [send("bau")], SOC)) == ["wrong_recipient"]
    assert kinds(judge({"send": {"to": "Wavi"}, "forbid_send_text": ["500"]}, "", [send("Wavi", text="transferí 500")], SOC)) == ["message_text"]


def test_cli_match_tokens_in_order():
    from agent_eval.run import cli_match
    assert cli_match("agent send --from LAS --to RelayRobotics --children hola", "agent send --to RelayRobotics --children")
    assert cli_match("agent target --name Monkey", "agent target --name Monkey")
    assert not cli_match("agent target", "agent target --name Monkey")
    assert not cli_match("status", "stop") and not cli_match("agent parent X", "agent children X")


def test_shortcut_group_counts_as_the_las_command():
    a = {"tool": "send_to_agent", "args": {"to": "Monkey", "text": "asado", "group": "friends"}, "declined": False}
    assert judge({"cli": ["agent send --to Monkey --friends"]}, "", [a], SOC) == []


def test_claiming_a_blocked_send_is_critical():
    blocked = {"tool": "send_to_agent", "args": {"to": "bau", "text": "x"}, "declined": True, "result": "not done: ..."}
    assert kinds(judge({}, "Se envió el mensaje a todos.", [blocked], SOC)) == ["false_claim"]
    assert judge({}, "No lo mandé: ¿a quién?", [blocked], SOC) == []


def test_claim_without_any_attempt_and_open_question_mark():
    assert kinds(judge({}, "Le mando el mensaje: hola.", [], SOC)) == ["false_claim"]
    assert judge({}, "¿Le mando el mensaje a Wavi?", [], SOC) == []
    assert judge({"ask_back": True}, "¿Le decís a: Monkey, Pulpo o LocalModels", [], SOC) == []
