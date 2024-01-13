FROM python:3.10-alpine
WORKDIR /usr/src/app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8443

CMD ["python3", "app.py"]