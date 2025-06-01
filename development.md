# Development

To get started, follow these steps:

1. Clone the repository

```bash
git clone https://github.com/bboonstra/solar.git
```

2. Install the dependencies using a virtual environment

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools
pip install -r requirements.txt
```

3. Configure the bot

Set up your environment.yaml and config.yaml files to match your environment.

```bash
cp environment.example.yaml environment.yaml
nano config.yaml
```

4. Run the application

```bash
python src/main.py
```
