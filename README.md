# MinerU 4.0.12 / vLLM 0.21.0 / CUDA 12.9（不预装模型权重）

镜像名称：`mineru:4.0.12-vllm0.21.0-cu129-no-models`

架构：`linux/amd64`（x86_64）。本次没有构建 ARM64 镜像。

基础镜像为指定的 Docker Hub 官方地址，并固定到实际拉取的摘要：

```text
docker.io/vllm/vllm-openai:v0.21.0-cu129@sha256:e7dedb8752ea2a6e28bd6e67f308f75704951e3c73cb57d321c835c352cf8584
```

容器实测系统为 **Ubuntu 22.04.5 LTS**，Python **3.12.13**，CUDA Toolkit **12.9.1**。该标签并非 Ubuntu 24.04。

## GitHub Release 分卷下载与合并

镜像 tar 按每卷 **1.5 GB（1,500,000,000 字节，十进制）**拆分，共 **8 卷**：前 7 卷各 1.5 GB，最后一卷 743,936,256 字节。每卷都低于 GitHub Release 附件的 2 GiB 限制。这是原始字节分卷，不是 ZIP/7z 压缩分卷。

下载 Release 中所有 `.tar.part001` 到 `.tar.part008`，以及 `parts-manifest.json`、`merge-parts.py`、`SHA256SUMS.parts.txt`、`SHA256SUMS.txt` 和本 README，放在同一个目录。保留原文件名，不要解压单个分卷。需要下载 Release 附件；GitHub 自动生成的 Source code ZIP/TAR 不包含镜像分卷。

在公司沙箱下载后，通过公司允许的文件导入流程转到内网。合并时需额外预留至少 12 GB 空间；包含所有分卷和合并后的 tar，合计约 22.49 GB。

推荐使用 Python 3 自动校验每卷并合并，Windows 执行：

```powershell
python .\merge-parts.py
```

Linux 执行：

```sh
python3 ./merge-parts.py
```

脚本成功后输出 `OK`，生成原始 tar；若某卷损坏会报告卷名，可只重新下载该卷。已有 tar 不会被覆盖。

Linux 也可使用系统命令校验、合并（当前目录不要放其他同名前缀分卷；目标 tar 如已存在应先移走）：

```sh
sha256sum -c SHA256SUMS.parts.txt && \
cat mineru-4.0.12-vllm0.21.0-cu129-linux-amd64-no-models.tar.part00[1-8] > mineru-4.0.12-vllm0.21.0-cu129-linux-amd64-no-models.tar && \
sha256sum -c SHA256SUMS.txt
```

完整 tar 为 **11,243,936,256 字节**，SHA256：

```text
ed5c14ea7bd202c3cd1f79c79dc9c0ff03f030d44bd97ca77012e7db8ffc3af8
```

## 导入与检查

以下命令在 tar 包所在目录执行：

```sh
docker load -i mineru-4.0.12-vllm0.21.0-cu129-linux-amd64-no-models.tar
docker run --rm mineru:4.0.12-vllm0.21.0-cu129-no-models mineru --version
docker run --rm --gpus all mineru:4.0.12-vllm0.21.0-cu129-no-models python3 -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))"
```

默认运行镜像会显示 MinerU 帮助。入口允许直接传入 `mineru`、`mineru-kit`、`python3` 或 `bash`。

## 模型权重

Dockerfile 不执行模型下载，也不复制本地模型。镜像内没有预装 MinerU 的 Torch bundle 或 VLM 权重；运行需要模型的解析任务前，应下载到外部持久目录，或挂载已经准备好的模型目录。

依赖包本身携带少量资源（例如 Magika 文件类型识别 ONNX、ONNX Runtime 示例、compressed-tensors 的 Hadamard 常量），这些属于原有软件依赖，不是 MinerU OCR/VLM 模型仓库。完整 vLLM/CUDA 环境仍保留，因此无模型镜像也有较大体积。

默认模型目录为 `/root/.mineru/models`。建议将 `/root/.mineru` 与 `/root/.cache` 分别持久化。先用下面命令查看模型目录与配置：

```sh
docker run --rm mineru:4.0.12-vllm0.21.0-cu129-no-models mineru-kit models --help
docker run --rm mineru:4.0.12-vllm0.21.0-cu129-no-models mineru config --help
```

后续模型下载使用官方命令，务必将模型目录挂载到宿主机持久存储后执行：

```sh
docker volume create mineru-home
docker volume create mineru-cache
docker run --rm -v mineru-home:/root/.mineru -v mineru-cache:/root/.cache mineru:4.0.12-vllm0.21.0-cu129-no-models mineru-kit models download --tier standard --small-backend torch --vlm-engine vllm -s modelscope
```

预设 `MINERU_MODEL_SMALL_BACKEND=torch`、`MINERU_MODEL_VLM_ENGINE=vllm`。不强制设置 `MINERU_MODEL_SOURCE=local`，便于首次准备模型；离线部署时可自行设置此变量为 `local`。

## API 与批处理

准备好模型并挂载模型持久目录后，可使用下列命令启动 API（额外添加所需模型目录挂载）：

```sh
docker run --rm --gpus all --ipc=host -p 8000:8000 -v mineru-home:/root/.mineru -v mineru-cache:/root/.cache -e MINERU_MODEL_SOURCE=local mineru:4.0.12-vllm0.21.0-cu129-no-models mineru-kit api-server --host 0.0.0.0 --port 8000 --tier standard
```

批量解析命令为 `mineru-kit parse /data/input.pdf -o /data/output --tier standard`，需要将输入输出目录挂载到 `/data`。这是 MinerU 4 的命令形式。

## 已执行的验证与限制

- MinerU 4.0.12、vLLM 0.21.0+cu129、Torch 2.11.0+cu129、Torchvision 0.26.0+cu129 版本检查通过。
- 禁网条件下，MinerU/模型下载命令帮助、vLLM/OpenCV/Gradio 导入检查通过。
- 本机 NVIDIA GeForce RTX 5070（Windows 驱动 591.86，经 Docker Desktop）CUDA 张量运算通过。
- 禁网条件下，MinerU API 以 basic tier 启动并响应 `/openapi.json`；FastAPI 监控 `/metrics` 返回 200。
- 安装后 Gradio 依赖 Starlette 1.x，与基础镜像的旧监控组件冲突，已将 `prometheus-fastapi-instrumentator` 固定为 8.1.0，并验证接口。
- `pip check` 仍报告基础镜像原有的 `pygobject 3.42.1 requires pycairo`；在原始基础镜像中也能复现。未使用 GTK 桌面功能；上述验证均已通过。
- 没有下载模型，没有执行完整文档模型推理、VLM 权重加载或目标服务器兼容性测试。

`verification.log` 保存测试结果，`requirements-installed.txt` 保存已安装依赖，`image-inspect.json` 保存镜像元数据，`build.log` 保存构建记录。安装步骤复用了本机对应基础镜像的已有构建缓存。

## 宿主机驱动说明

“550.x 是 CUDA 12.x 通用最低要求”并不准确。NVIDIA 的 CUDA 12.x 小版本兼容下限为 Linux 525.60.13，但受功能和 PTX 等限制，不能据此保证 vLLM 可运行。CUDA 12.9 Update 1 对应 Linux 驱动版本为 575.57.08，建议部署时以该版本或更新版本为基线，并在实际 GPU 上验证。这是部署建议，不是所有 GPU/兼容模式下统一的硬性最低值。

参考：

- [MinerU 官方 China Dockerfile](https://github.com/opendatalab/MinerU/blob/master/docker/china/Dockerfile)
- [NVIDIA CUDA 小版本兼容说明](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)
- [CUDA 12.9 Update 1 发布说明](https://docs.nvidia.com/cuda/archive/12.9.1/cuda-toolkit-release-notes/index.html)

重新构建：`docker build --platform linux/amd64 -t mineru:4.0.12-vllm0.21.0-cu129-no-models .`。MinerU 版本、基础镜像和关键 GPU 软件版本固定，普通依赖并未全部锁定；重建时若依赖发生变化，需重新运行验证。


进入容器后执行：
mineru-kit api-server --host 0.0.0.0 --port 8000 --tier standard
需要事先准备好模型权重；这个镜像未预装模型，可以先运行：
mineru-kit models download --tier standard --small-backend torch --vlm-engine vllm -s modelscope
如果模型已准备好，启动前可设置为只使用本地模型：
export MINERU_MODEL_SOURCE=local
容器创建时需带上 --gpus all --ipc=host -p 8000:8000，并持久化模型目录 /root/.mineru。API 启动后，可访问 http://宿主机IP:8000/docs 查看接口文档。
