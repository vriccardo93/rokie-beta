FROM python:3.12-slim
WORKDIR /app
COPY rokie_field_app.py /app/rokie_field_app.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/rokie_field_app.py"]
