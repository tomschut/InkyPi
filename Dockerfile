FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git curl chromium fonts-noto-color-emoji libheif1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r install/requirements-dev.txt && bash install/update_vendors.sh
RUN cp device.json src/config/device.json
EXPOSE 80
CMD ["python", "src/inkypi.py"]
