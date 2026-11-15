.PHONY: all install data build analyze clean

all: data build analyze

install:
	pip install -r requirements.txt

data:
	python scripts/generate_data.py

build:
	mkdir -p warehouse
	cd dbt && dbt build --profiles-dir .

analyze:
	python scripts/analyze.py

docs:
	cd dbt && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .

clean:
	rm -rf warehouse dbt/target dbt/logs data/raw/*.csv
