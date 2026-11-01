# Based on https://github.com/opendatalab/MinerU/blob/master/docker/china/Dockerfile
# No model weights are downloaded during this build.
ARG BASE_IMAGE=docker.io/vllm/vllm-openai:v0.21.0-cu129@sha256:e7dedb8752ea2a6e28bd6e67f308f75704951e3c73cb57d321c835c352cf8584
FROM ${BASE_IMAGE}

RUN apt-get update && \
    apt-get install -y \
        libgl1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install -U "mineru[torch]==4.0.12" -i https://mirrors.aliyun.com/pypi/simple --break-system-packages && \
    python3 -m pip cache purge

# Gradio now requires Starlette 1.x; update the base image's instrumentation
# to a compatible release, preserving Gradio's supported dependency range.
RUN python3 -m pip install --no-cache-dir 'prometheus-fastapi-instrumentator==8.1.0' \
        -i https://mirrors.aliyun.com/pypi/simple --break-system-packages

# Fail rather than silently ship a different GPU software stack.
RUN python3 -c "import importlib.metadata as m; assert m.version('mineru') == '4.0.12'; assert m.version('vllm') == '0.21.0+cu129'; assert m.version('torch') == '2.11.0+cu129'; assert m.version('torchvision') == '0.26.0+cu129'"

ENV MINERU_MODEL_SMALL_BACKEND=torch \
    MINERU_MODEL_VLM_ENGINE=vllm

# Leave model source configurable: download later or mount external weights.
WORKDIR /workspace
ENTRYPOINT ["/bin/bash", "-c", "exec \"$@\"", "--"]
CMD ["mineru", "--help"]
