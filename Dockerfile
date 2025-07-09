FROM python:3.10-alpine
COPY polar-export.py requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
CMD sleep infinity
