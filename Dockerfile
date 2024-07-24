FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock /app/

RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

COPY . /app/

EXPOSE 5000

CMD ["poetry", "run", "python", "main.py"]
