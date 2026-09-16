# Untrainable

## Installation
```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip intall django
django-admin startproject untrianable .
python manage.py check
```

## To run
```
python manage.py migrate
python manage.py runserver
```

## To make a new webpage
```
python manage.py startapp NAME_OF_WEBPAGE
```

## Extra 
https://huggingface.co/datasets/sm4rtdev/reddit_dataset_240?utm_source=chatgpt.com

Taxonomy Labels for classification 
https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%203.1.tsv

## Docker - for postgres 16 db
Also an application called TablePlus for macos is good at visualising the data if would like to visualise it much better

```
docker stop my-postgres
docker start my-postgres
```
