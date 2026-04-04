FROM python:3.11
WORKDIR /code
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
# Port 7860 is the default for HF Spaces
EXPOSE 7860
CMD ["python", "main.py"]