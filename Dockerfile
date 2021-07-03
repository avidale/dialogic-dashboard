# STEP 1: Install base image. Optimized for Python.
FROM python:3.7-slim-buster
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["python", "main.py"]
