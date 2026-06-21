"""Abstract provider interface."""
from abc import ABC, abstractmethod
from benchmark.metrics import Result
from benchmark.tasks import Task


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def run(self, model_id: str, task: Task) -> Result:
        """Run a single task on a model and return a Result."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return available model IDs for this provider."""
        ...
