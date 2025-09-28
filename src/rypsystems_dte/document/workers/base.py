"""
Base Worker classes for document processing pipeline.

Provides abstract base classes and common functionality for all document workers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum
import logging
from pydantic import BaseModel, Field

from ...dte.document import BaseDocument


logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Worker execution status."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


class WorkerMessage(BaseModel):
    """Worker message for warnings, errors, and information."""
    level: str = Field(..., description="Message level (info, warning, error)")
    code: str = Field(..., description="Message code for categorization")
    message: str = Field(..., description="Human-readable message")
    field: Optional[str] = Field(None, description="Field related to message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class WorkerResult(BaseModel):
    """Result of worker execution."""
    model_config = {"arbitrary_types_allowed": True}

    worker_name: str = Field(..., description="Name of worker that produced result")
    status: WorkerStatus = Field(..., description="Execution status")
    document: Optional[BaseDocument] = Field(None, description="Processed document")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional result data")
    messages: List[WorkerMessage] = Field(default_factory=list, description="Processing messages")
    execution_time: float = Field(0.0, description="Execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="Execution timestamp")

    def add_message(self, level: str, code: str, message: str, field: Optional[str] = None, **details):
        """Add a message to the result."""
        self.messages.append(WorkerMessage(
            level=level,
            code=code,
            message=message,
            field=field,
            details=details
        ))

    def add_error(self, code: str, message: str, field: Optional[str] = None, **details):
        """Add an error message."""
        self.add_message("error", code, message, field, **details)

    def add_warning(self, code: str, message: str, field: Optional[str] = None, **details):
        """Add a warning message."""
        self.add_message("warning", code, message, field, **details)

    def add_info(self, code: str, message: str, field: Optional[str] = None, **details):
        """Add an info message."""
        self.add_message("info", code, message, field, **details)

    def has_errors(self) -> bool:
        """Check if result has error messages."""
        return any(msg.level == "error" for msg in self.messages)

    def has_warnings(self) -> bool:
        """Check if result has warning messages."""
        return any(msg.level == "warning" for msg in self.messages)

    def get_errors(self) -> List[WorkerMessage]:
        """Get all error messages."""
        return [msg for msg in self.messages if msg.level == "error"]

    def get_warnings(self) -> List[WorkerMessage]:
        """Get all warning messages."""
        return [msg for msg in self.messages if msg.level == "warning"]


class BaseWorker(ABC):
    """
    Abstract base worker for document processing.

    All workers must implement the process method and can optionally
    implement pre/post processing hooks.
    """

    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize worker.

        Args:
            name: Worker name (defaults to class name)
            config: Worker configuration
        """
        self.name = name or self.__class__.__name__
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """
        Process a document.

        Args:
            document: Document to process
            context: Additional processing context

        Returns:
            Worker result with processed document and messages
        """
        pass

    def pre_process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Pre-processing hook called before main processing.

        Args:
            document: Document to process
            context: Processing context

        Returns:
            True to continue processing, False to skip
        """
        return True

    def post_process(self, result: WorkerResult, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """
        Post-processing hook called after main processing.

        Args:
            result: Processing result
            context: Processing context

        Returns:
            Modified result
        """
        return result

    def should_process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if worker should process this document.

        Args:
            document: Document to check
            context: Processing context

        Returns:
            True if worker should process document
        """
        return True

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default."""
        return self.config.get(key, default)

    def validate_config(self) -> List[str]:
        """
        Validate worker configuration.

        Returns:
            List of configuration errors
        """
        return []

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', config={self.config})"


class WorkerPipeline:
    """
    Pipeline for executing multiple workers in sequence.

    Provides orchestration, error handling, and result aggregation
    for document processing workflows.
    """

    def __init__(self, workers: Optional[List[BaseWorker]] = None):
        """
        Initialize pipeline.

        Args:
            workers: List of workers to execute
        """
        self.workers = workers or []
        self.logger = logging.getLogger(f"{__name__}.WorkerPipeline")

    def add_worker(self, worker: BaseWorker) -> 'WorkerPipeline':
        """
        Add worker to pipeline.

        Args:
            worker: Worker to add

        Returns:
            Self for chaining
        """
        self.workers.append(worker)
        return self

    def remove_worker(self, worker_name: str) -> bool:
        """
        Remove worker by name.

        Args:
            worker_name: Name of worker to remove

        Returns:
            True if worker was removed
        """
        for i, worker in enumerate(self.workers):
            if worker.name == worker_name:
                del self.workers[i]
                return True
        return False

    def process(
        self,
        document: BaseDocument,
        context: Optional[Dict[str, Any]] = None,
        stop_on_error: bool = True
    ) -> List[WorkerResult]:
        """
        Process document through pipeline.

        Args:
            document: Document to process
            context: Processing context
            stop_on_error: Stop pipeline on first error

        Returns:
            List of worker results
        """
        results = []
        current_document = document
        pipeline_context = context or {}

        self.logger.info(f"Starting pipeline with {len(self.workers)} workers")

        for worker in self.workers:
            try:
                # Check if worker should process document
                if not worker.should_process(current_document, pipeline_context):
                    self.logger.info(f"Skipping worker {worker.name}")
                    result = WorkerResult(
                        worker_name=worker.name,
                        status=WorkerStatus.SKIPPED,
                        document=current_document
                    )
                    result.add_info("worker_skipped", f"Worker {worker.name} skipped")
                    results.append(result)
                    continue

                # Pre-processing
                if not worker.pre_process(current_document, pipeline_context):
                    self.logger.info(f"Worker {worker.name} pre-processing failed, skipping")
                    result = WorkerResult(
                        worker_name=worker.name,
                        status=WorkerStatus.SKIPPED,
                        document=current_document
                    )
                    result.add_warning("pre_process_failed", f"Worker {worker.name} pre-processing failed")
                    results.append(result)
                    continue

                # Main processing
                start_time = datetime.now()
                result = worker.process(current_document, pipeline_context)
                end_time = datetime.now()
                result.execution_time = (end_time - start_time).total_seconds()

                # Post-processing
                result = worker.post_process(result, pipeline_context)

                results.append(result)

                # Update current document if processing was successful
                if result.status == WorkerStatus.SUCCESS and result.document:
                    current_document = result.document

                # Stop on error if configured
                if stop_on_error and result.has_errors():
                    self.logger.error(f"Pipeline stopped due to errors in worker {worker.name}")
                    break

                self.logger.info(f"Worker {worker.name} completed with status {result.status}")

            except Exception as e:
                self.logger.exception(f"Unexpected error in worker {worker.name}")
                result = WorkerResult(
                    worker_name=worker.name,
                    status=WorkerStatus.ERROR,
                    document=current_document
                )
                result.add_error("unexpected_error", f"Unexpected error: {str(e)}", exception=str(e))
                results.append(result)

                if stop_on_error:
                    break

        self.logger.info(f"Pipeline completed with {len(results)} results")
        return results

    def validate_pipeline(self) -> List[str]:
        """
        Validate pipeline configuration.

        Returns:
            List of validation errors
        """
        errors = []

        if not self.workers:
            errors.append("Pipeline has no workers")

        for worker in self.workers:
            worker_errors = worker.validate_config()
            for error in worker_errors:
                errors.append(f"Worker {worker.name}: {error}")

        return errors

    def get_worker(self, name: str) -> Optional[BaseWorker]:
        """
        Get worker by name.

        Args:
            name: Worker name

        Returns:
            Worker instance or None
        """
        for worker in self.workers:
            if worker.name == name:
                return worker
        return None

    def __len__(self) -> int:
        return len(self.workers)

    def __iter__(self):
        return iter(self.workers)

    def __str__(self) -> str:
        worker_names = [worker.name for worker in self.workers]
        return f"WorkerPipeline({worker_names})"