FROM python:3.13-slim-bookworm
ARG INKYPI_REF=main
RUN apt-get update && apt-get install -y --no-install-recommends git curl chromium fonts-noto-color-emoji libheif1 && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/tomschut/InkyPi.git /app && cd /app && git checkout "$INKYPI_REF"
WORKDIR /app
RUN pip install --no-cache-dir -r install/requirements-dev.txt && bash install/update_vendors.sh
COPY device.json /app/device.json
RUN cp /app/device.json /app/src/config/device.json
EXPOSE 80
ARG BUILD_VERSION=0.1.0
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
COPY run.py /run.py
CMD ["python", "/run.py"]
