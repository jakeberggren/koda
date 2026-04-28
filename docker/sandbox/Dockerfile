FROM docker/sandbox-templates:shell

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        fd-find \
        git \
        jq \
        less \
        ripgrep \
    && rm -rf /var/lib/apt/lists/*

USER agent
ARG KODA_VERSION=latest
ENV KODA_VERSION=${KODA_VERSION}
ENV KODA_BASH_EXECUTION_SANDBOX=host
ENV KODA_PROVIDER=openai
ENV OPENAI_API_KEY=proxy-managed
ENV PATH="/home/agent/.local/bin:${PATH}"

RUN curl -fsSL https://raw.githubusercontent.com/jakeberggren/koda/main/install.sh | bash
