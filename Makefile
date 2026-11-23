.PHONY: install run test lint format data-check docker

install:
	pip install -r requirements-dev.txt

run:
	streamlit run app.py

test:
	python -m pytest -q

lint:
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check --fix .

data-check:
	python scripts/validate_data.py

docker:
	docker build -t fed-bi-rupiah-monitor . && docker run --rm -p 8501:8501 fed-bi-rupiah-monitor
