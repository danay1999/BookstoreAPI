FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py /app/app.py
EXPOSE 8080
CMD ["python","-m","uvicorn","app:app","--host","0.0.0.0","--port","8080"]
