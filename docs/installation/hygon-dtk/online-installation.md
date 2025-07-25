# Online Installation

## Supported Devices

- [x] Hygon DCUs (K100_AI (Verified), Z100/Z100L/K100(Not Verified))

## Supported Platforms

| OS    | Arch  | Supported methods                                                                                        |
| ----- | ----- | -------------------------------------------------------------------------------------------------------- |
| Linux | AMD64 | [Docker Installation](#docker-installation) (Recommended)<br>[Installation Script](#installation-scriptdeprecated) |

## Prerequisites

- [Port Requirements](../installation-requirements.md#port-requirements)
- CPU support for llama-box backend: AMD64 with AVX2

Check if the CPU is supported:

```bash
lscpu | grep avx2
```

- [DCU Driver rock-6.3](https://developer.sourcefind.cn/tool/)

Check if the driver is installed:

```bash
lsmod | grep dcu
```

## Docker Installation

### Supported backends

- [x] vLLM (Only supports K100_AI)
- [x] llama-box

### Prerequisites

- [Docker](https://docs.docker.com/engine/install/)

### Run GPUStack

Run the following command to start the GPUStack server **and built-in worker** (host network mode is recommended):

```bash
docker run -d --name gpustack \
    --restart=unless-stopped \
    --device=/dev/kfd \
    --device=/dev/mkfd \
    --device=/dev/dri \
    -v /opt/hyhal:/opt/hyhal:ro \
    --network=host \
    --ipc=host \
    --group-add video \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    -v gpustack-data:/var/lib/gpustack \
    gpustack/gpustack:latest-dcu
```

If you need to change the default server port 80, please use the `--port` parameter:

```bash
docker run -d --name gpustack \
    --restart=unless-stopped \
    --device=/dev/kfd \
    --device=/dev/mkfd \
    --device=/dev/dri \
    -v /opt/hyhal:/opt/hyhal:ro \
    --network=host \
    --ipc=host \
    --group-add video \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    -v gpustack-data:/var/lib/gpustack \
    gpustack/gpustack:latest-dcu \
    --port 9090
```

If other ports are in conflict, or if you want to customize startup options, refer to the [CLI Reference](../../cli-reference/start.md) for available flags and configuration instructions.

Check if the startup logs are normal:

```bash
docker logs -f gpustack
```

If the logs are normal, open `http://your_host_ip` in the browser to access the GPUStack UI. Log in to GPUStack with username `admin` and the default password. You can run the following command to get the password for the default setup:

```bash
docker exec -it gpustack cat /var/lib/gpustack/initial_admin_password
```

### (Optional) Add Worker

You can add more GPU nodes to GPUStack to form a GPU cluster. You need to add workers on other GPU nodes and specify the `--server-url` and `--token` parameters to join GPUStack.

To get the token used for adding workers, run the following command on the GPUStack **server node**:

```bash
docker exec -it gpustack cat /var/lib/gpustack/token
```

To start GPUStack as a worker, and **register it with the GPUStack server**, run the following command on the **worker node**. Be sure to replace the URL and token with your specific values:

```bash
docker run -d --name gpustack \
    --restart=unless-stopped \
    --device=/dev/kfd \
    --device=/dev/mkfd \
    --device=/dev/dri \
    -v /opt/hyhal:/opt/hyhal:ro \
    --network=host \
    --ipc=host \
    --group-add video \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    -v gpustack-data:/var/lib/gpustack \
    gpustack/gpustack:latest-dcu \
    --server-url http://your_gpustack_url --token your_gpustack_token
```

!!! note

    1. **Heterogeneous cluster is supported.** No matter what type of device it is, you can add it to the current GPUStack as a worker by specifying the `--server-url` and `--token` parameters.

    2. You can set additional flags for the `gpustack start` command by appending them to the docker run command.
    For configuration details, please refer to the [CLI Reference](../../cli-reference/start.md).

    3. You can either use the `--ipc=host` flag or `--shm-size` flag to allow the container to access the host’s shared memory. It is used by vLLM and pyTorch to share data between processes under the hood, particularly for tensor parallel inference.

## Installation Script(Deprecated)

!!! warning
      The installation script method is deprecated as of version 0.7. We recommend using Docker on Linux, and the [desktop installer](https://gpustack.ai/) on macOS or Windows.

### Supported backends

- [x] llama-box

### Prerequites

- [DCU Toolkit 25.04](https://developer.sourcefind.cn/tool/)

Check if the GPU is listed as an agent:

```bash
rocminfo
```

Check `hy-smi`:

```bash
/opt/hyhal/bin/hy-smi -i --showmeminfo vram --showpower --showserial --showuse --showtemp --showproductname --showuniqueid --json
```

### Run GPUStack

GPUStack provides a script to install it as a service with default port 80.

```bash
curl -sfL https://get.gpustack.ai | sh -s -
```

To configure additional environment variables and startup flags when running the script, refer to the [Installation Script](../installation-script.md).

After installed, ensure that the GPUStack startup logs are normal:

```bash
tail -200f /var/log/gpustack.log
```

If the startup logs are normal, open `http://your_host_ip` in the browser to access the GPUStack UI. Log in to GPUStack with username `admin` and the default password. You can run the following command to get the password for the default setup:

```bash
cat /var/lib/gpustack/initial_admin_password
```

If you specify the `--data-dir` parameter to set the data directory, the `initial_admin_password` file will be located in the specified directory.

### (Optional) Add Worker

To add workers to the GPUStack cluster, you need to specify the server URL and authentication token when installing GPUStack on the workers.

To get the token used for adding workers, run the following command on the GPUStack **server node**:

```bash
cat /var/lib/gpustack/token
```

If you specify the `--data-dir` parameter to set the data directory, the `token` file will be located in the specified directory.

To install GPUStack and start it as a worker, and **register it with the GPUStack server**, run the following command on the **worker node**. Be sure to replace the URL and token with your specific values:

```bash
curl -sfL https://get.gpustack.ai | sh -s - --server-url http://your_gpustack_url --token your_gpustack_token
```

After installed, ensure that the GPUStack startup logs are normal:

```bash
tail -200f /var/log/gpustack.log
```
