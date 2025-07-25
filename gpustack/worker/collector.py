import logging
from typing import Optional
from gpustack.client.generated_clientset import ClientSet
from gpustack.detectors.base import GPUDetectExepction
from gpustack.detectors.custom.custom import Custom
from gpustack.detectors.detector_factory import DetectorFactory
from gpustack.policies.base import Allocated
from gpustack.schemas.models import ComputedResourceClaim
from gpustack.schemas.workers import (
    RPCServer,
    MountPoint,
    WorkerStateEnum,
)
import socket
from gpustack.schemas.workers import WorkerStatus, Worker

logger = logging.getLogger(__name__)


class WorkerStatusCollector:

    def __init__(
        self,
        worker_ip: str,
        worker_name: str,
        worker_port: int,
        clientset: ClientSet = None,
        worker_manager=None,
        gpu_devices=None,
        system_info=None,
    ):
        self._worker_name = worker_name
        self._hostname = socket.gethostname()
        self._worker_ip = worker_ip
        self._worker_port = worker_port
        self._clientset = clientset
        self._worker_manager = worker_manager
        if self._worker_manager:
            self._worker_uuid = self._worker_manager.get_worker_uuid()

        if gpu_devices and system_info:
            self._detector_factory = DetectorFactory(
                device="custom",
                gpu_detectors={"custom": [Custom(gpu_devices=gpu_devices)]},
                system_info_detector=Custom(system_info=system_info),
            )
        elif gpu_devices:
            self._detector_factory = DetectorFactory(
                device="custom",
                gpu_detectors={"custom": [Custom(gpu_devices=gpu_devices)]},
            )
        elif system_info:
            self._detector_factory = DetectorFactory(
                system_info_detector=Custom(system_info=system_info)
            )
        else:
            self._detector_factory = DetectorFactory()

    """A class for collecting worker status information."""

    def collect(self, initial: bool = False) -> Worker:  # noqa: C901
        """Collect worker status information."""
        status = WorkerStatus()
        state_message = None
        try:
            system_info = self._detector_factory.detect_system_info()
            status.cpu = system_info.cpu
            status.memory = system_info.memory
            status.swap = system_info.swap
            status.filesystem = system_info.filesystem
            status.os = system_info.os
            status.kernel = system_info.kernel
            status.uptime = system_info.uptime
        except Exception as e:
            logger.error(f"Failed to detect system info: {e}")

        if not initial:
            try:
                gpu_devices = self._detector_factory.detect_gpus()
                status.gpu_devices = gpu_devices
            except GPUDetectExepction as e:
                state_message = str(e)
            except Exception as e:
                logger.error(f"Failed to detect GPU devices: {e}")
        self._inject_unified_memory(status)
        self._inject_computed_filesystem_usage(status)
        self._inject_allocated_resource(status)

        if self._worker_manager is not None:
            server_processes = self._worker_manager.get_rpc_servers()
            rps_server = {}
            for gpu_index, process in server_processes.items():
                rps_server[gpu_index] = RPCServer(
                    pid=process.process.pid, port=process.port, gpu_index=gpu_index
                )
            status.rpc_servers = rps_server

        state = (
            WorkerStateEnum.NOT_READY
            if initial or state_message
            else WorkerStateEnum.READY
        )

        return Worker(
            name=self._worker_name,
            hostname=self._hostname,
            ip=self._worker_ip,
            port=self._worker_port,
            state=state,
            status=status,
            state_message=state_message,
            worker_uuid=self._worker_uuid if self._worker_manager else None,
        )

    def _inject_unified_memory(self, status: WorkerStatus):
        is_unified_memory = False
        if status.gpu_devices is not None and len(status.gpu_devices) != 0:
            is_unified_memory = status.gpu_devices[0].memory.is_unified_memory

        if status.memory is not None:
            status.memory.is_unified_memory = is_unified_memory

    def _inject_computed_filesystem_usage(self, status: WorkerStatus):
        if (
            status.os is None
            or "Windows" not in status.os.name
            or status.filesystem is None
        ):
            return

        try:
            computed = MountPoint(
                name="computed",
                mount_point="/",
                total=0,
                used=0,
                free=0,
                available=0,
            )
            for mountpoint in status.filesystem:
                computed.total = computed.total + mountpoint.total
                computed.used = computed.used + mountpoint.used
                computed.free = computed.free + mountpoint.free
                computed.available = computed.available + mountpoint.available

            # inject computed filesystem usage
            status.filesystem.append(computed)
        except Exception as e:
            logger.error(f"Failed to inject filesystem usage: {e}")

    def _inject_allocated_resource(  # noqa: C901
        self, status: WorkerStatus
    ) -> Allocated:
        allocated = Allocated(ram=0, vram={})
        try:
            model_instances = self._clientset.model_instances.list()
            for model_instance in model_instances.items:
                if (
                    model_instance.distributed_servers
                    and model_instance.distributed_servers.subordinate_workers
                ):
                    for (
                        subworker
                    ) in model_instance.distributed_servers.subordinate_workers:
                        if subworker.worker_name != self._worker_name:
                            continue

                        aggregate_computed_resource_claim_allocated(
                            allocated, subworker.computed_resource_claim
                        )

                if model_instance.worker_name != self._worker_name:
                    continue

                aggregate_computed_resource_claim_allocated(
                    allocated, model_instance.computed_resource_claim
                )

            # inject allocated resources
            if status.memory is not None:
                status.memory.allocated = allocated.ram
            if status.gpu_devices is not None:
                for i, device in enumerate(status.gpu_devices):
                    if device.index in allocated.vram:
                        status.gpu_devices[i].memory.allocated = allocated.vram[
                            device.index
                        ]
                    else:
                        status.gpu_devices[i].memory.allocated = 0
        except Exception as e:
            logger.error(f"Failed to inject allocated resources: {e}")


def aggregate_computed_resource_claim_allocated(
    allocated: Allocated, computed_resource_claim: Optional[ComputedResourceClaim]
):
    """Aggregate allocated resources from a ComputedResourceClaim into Allocated."""
    if computed_resource_claim is None:
        return

    if computed_resource_claim.ram:
        allocated.ram += computed_resource_claim.ram

    for gpu_index, vram in (computed_resource_claim.vram or {}).items():
        allocated.vram[gpu_index] = (allocated.vram.get(gpu_index) or 0) + vram
