"""Project Templates — scaffold projects from built-in and custom templates."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import CONFIG_DIR

CUSTOM_TEMPLATES_DIR = CONFIG_DIR / "templates"

# ── Built-in template definitions ────────────────────────────────────

BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "python-package": {
        "description": "Modern Python package with pyproject.toml, tests, and CI",
        "files": {
            "pyproject.toml": '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"
authors = [
    {{name = "{{author}}", email = "{{email}}"}},
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov", "ruff", "mypy"]

[project.scripts]
{{project_name}} = "{{module_name}}.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov={{module_name}}"

[tool.ruff]
line-length = 88
target-version = "py38"

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
''',
            "README.md": '''# {{project_name}}

{{description}}

## Installation

```bash
pip install {{project_name}}
```

## Usage

```python
from {{module_name}} import hello

print(hello())
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy .
```

## License

MIT
''',
            "src/{{module_name}}/__init__.py": '''"""{{description}}."""

__version__ = "0.1.0"


def hello() -> str:
    """Return a greeting message."""
    return "Hello from {{project_name}}!"
''',
            "src/{{module_name}}/cli.py": '''"""Command-line interface for {{project_name}}."""

import argparse
import sys

from . import __version__, hello


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(prog="{{project_name}}", description="{{description}}")
    parser.add_argument("--version", action="version", version=f"%(prog)s {{__version__}}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args(argv)

    print(hello())
    return 0


if __name__ == "__main__":
    sys.exit(main())
''',
            "tests/__init__.py": "",
            "tests/test_main.py": '''"""Tests for {{module_name}}."""

from {{module_name}} import hello


def test_hello():
    result = hello()
    assert isinstance(result, str)
    assert "Hello" in result
''',
            ".gitignore": """__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.env
*.so
""",
            "Makefile": '''.PHONY: install test lint format clean

install:
\tpip install -e ".[dev]"

test:
\tpytest

lint:
\truff check .
\tmypy .

format:
\truff format .

clean:
\trm -rf build dist *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage
''',
        },
        "post_instructions": [
            "Run `pip install -e \".[dev]\"` to install in development mode.",
            "Run `pytest` to verify tests pass.",
            "Start coding in `src/{{module_name}}/`!",
        ],
    },
    "fastapi-api": {
        "description": "FastAPI REST API with auth, DB, and Docker",
        "files": {
            "pyproject.toml": '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy>=2.0",
    "alembic>=1.12",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "pydantic>=2.5",
    "python-multipart>=0.0.6",
    "httpx>=0.25",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio", "httpx"]
''',
            "app/__init__.py": "",
            "app/main.py": '''"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import api_router
from .database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="{{project_name}}",
    description="{{description}}",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
''',
            "app/database.py": '''"""Database configuration using SQLAlchemy."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
''',
            "app/models.py": '''"""Database models."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    owner_id = Column(Integer, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
''',
            "app/routes.py": '''"""API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import Item, User

api_router = APIRouter()


@api_router.get("/items")
async def list_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(Item).offset(skip).limit(limit).all()
    return items


@api_router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_item(title: str, description: str = "", db: Session = Depends(get_db)):
    item = Item(title=title, description=description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
''',
            "Dockerfile": '''FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
''',
            "docker-compose.yml": '''version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./app.db
    volumes:
      - ./app.db:/app/app.db
''',
            ".gitignore": """__pycache__/
*.py[cod]
*.egg-info/
.env
*.db
.pytest_cache/
""",
        },
        "post_instructions": [
            "Run `pip install -e \".[dev]\"` to install dependencies.",
            "Start the server: `uvicorn app.main:app --reload`.",
            "API docs at http://localhost:8000/docs",
            "Run with Docker: `docker compose up`",
        ],
    },
    "flask-api": {
        "description": "Flask REST API with SQLAlchemy",
        "files": {
            "requirements.txt": """flask>=3.0
flask-sqlalchemy>=3.1
flask-cors>=4.0
python-dotenv>=1.0
""",
            "app.py": '''"""Flask application entry point."""

import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
CORS(app)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")

    def to_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description}


with app.app_context():
    db.create_all()


@app.route("/api/items", methods=["GET"])
def list_items():
    items = Item.query.all()
    return jsonify([i.to_dict() for i in items])


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.json
    item = Item(title=data["title"], description=data.get("description", ""))
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
''',
            ".gitignore": """__pycache__/
*.py[cod]
.env
*.db
instance/
""",
        },
        "post_instructions": [
            "Install dependencies: `pip install -r requirements.txt`",
            "Run: `python app.py`",
            "API available at http://localhost:5000/api/items",
        ],
    },
    "cli-tool": {
        "description": "Python CLI tool with click",
        "files": {
            "pyproject.toml": '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{{project_name}}"
version = "0.1.0"
description = "{{description}}"
requires-python = ">=3.8"
dependencies = ["click>=8.1", "rich>=13.0"]

[project.scripts]
{{project_name}} = "{{module_name}}.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov"]
''',
            "src/{{module_name}}/__init__.py": '''"""{{description}}."""
__version__ = "0.1.0"
''',
            "src/{{module_name}}/cli.py": '''"""CLI entry point for {{project_name}}."""

import click


@click.group()
@click.version_option(package_name="{{module_name}}")
def main():
    """{{description}}."""
    pass


@main.command()
@click.argument("name", default="World")
def hello(name: str):
    """Say hello."""
    click.echo(f"Hello, {name}!")


@main.command()
@click.option("--count", "-n", default=1, help="Number of times to repeat")
@click.argument("message")
def repeat(count: int, message: str):
    """Repeat a message."""
    for _ in range(count):
        click.echo(message)


if __name__ == "__main__":
    main()
''',
            "tests/__init__.py": "",
            "tests/test_cli.py": '''"""Tests for CLI."""
from click.testing import CliRunner
from {{module_name}}.cli import main

def test_hello():
    runner = CliRunner()
    result = runner.invoke(main, ["hello", "Test"])
    assert result.exit_code == 0
    assert "Hello, Test!" in result.output
''',
            ".gitignore": """__pycache__/
*.egg-info/
dist/
.pytest_cache/
""",
        },
        "post_instructions": [
            "Install: `pip install -e \".[dev]\"`",
            "Run: `{{project_name}} hello`",
            "Test: `pytest`",
        ],
    },
    "react-app": {
        "description": "React + TypeScript + Vite",
        "files": {
            "package.json": '''{
  "name": "{{project_name}}",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "eslint": "^8.55.0"
  }
}
''',
            "tsconfig.json": '''{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
''',
            "vite.config.ts": '''import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
})
''',
            "index.html": '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{project_name}}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''',
            "src/main.tsx": '''import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
''',
            "src/App.tsx": '''import { useState } from "react"

function App() {
  const [count, setCount] = useState(0)

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
      <h1>{{project_name}}</h1>
      <button onClick={() => setCount(c => c + 1)}>
        Count: {count}
      </button>
    </div>
  )
}

export default App
''',
            "src/vite-env.d.ts": '''/// <reference types="vite/client" />
''',
            ".gitignore": """node_modules/
dist/
.env
*.local
""",
        },
        "post_instructions": [
            "Install: `npm install`",
            "Run: `npm run dev`",
            "Build: `npm run build`",
        ],
    },
    "nextjs-app": {
        "description": "Next.js with App Router",
        "files": {
            "package.json": '''{
  "name": "{{project_name}}",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.2.0",
    "typescript": "^5.3.0",
    "eslint": "^8.55.0",
    "eslint-config-next": "14.0.0"
  }
}
''',
            "tsconfig.json": '''{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
''',
            "next.config.js": '''/** @type {import('next').NextConfig} */
const nextConfig = {}
module.exports = nextConfig
''',
            "src/app/layout.tsx": '''export const metadata = {
  title: "{{project_name}}",
  description: "{{description}}",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
''',
            "src/app/page.tsx": '''export default function Home() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui" }}>
      <h1>Welcome to {{project_name}}</h1>
      <p>Get started by editing src/app/page.tsx</p>
    </main>
  )
}
''',
            ".gitignore": """node_modules/
.next/
out/
.env*.local
""",
        },
        "post_instructions": [
            "Install: `npm install`",
            "Run: `npm run dev`",
            "Open http://localhost:3000",
        ],
    },
    "express-api": {
        "description": "Express.js REST API",
        "files": {
            "package.json": '''{
  "name": "{{project_name}}",
  "version": "0.1.0",
  "scripts": {
    "dev": "node --watch src/index.js",
    "start": "node src/index.js"
  },
  "dependencies": {
    "express": "^4.18.0",
    "cors": "^2.8.5",
    "dotenv": "^16.3.0"
  }
}
''',
            "src/index.js": '''import express from "express"
import cors from "cors"
import dotenv from "dotenv"

dotenv.config()

const app = express()
const PORT = process.env.PORT || 3000

app.use(cors())
app.use(express.json())

// In-memory store
let items = []
let nextId = 1

app.get("/health", (req, res) => {
  res.json({ status: "ok" })
})

app.get("/api/items", (req, res) => {
  res.json(items)
})

app.post("/api/items", (req, res) => {
  const { title, description } = req.body
  const item = { id: nextId++, title, description: description || "" }
  items.push(item)
  res.status(201).json(item)
})

app.get("/api/items/:id", (req, res) => {
  const item = items.find(i => i.id === parseInt(req.params.id))
  if (!item) return res.status(404).json({ error: "Not found" })
  res.json(item)
})

app.delete("/api/items/:id", (req, res) => {
  items = items.filter(i => i.id !== parseInt(req.params.id))
  res.status(204).send()
})

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`)
})
''',
            ".gitignore": """node_modules/
.env
""",
        },
        "post_instructions": [
            "Install: `npm install`",
            "Run: `npm run dev`",
            "API at http://localhost:3000/api/items",
        ],
    },
    "django-app": {
        "description": "Django with Django REST Framework",
        "files": {
            "requirements.txt": """django>=5.0
djangorestframework>=3.14
django-cors-headers>=4.3
python-dotenv>=1.0
""",
            "manage.py": '''#!/usr/bin/env python
"""Django's command-line utility."""
import os
import sys

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{{module_name}}.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
''',
            "{{module_name}}/__init__.py": "",
            "{{module_name}}/settings.py": '''"""Django settings for {{project_name}}."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dev-key-change-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "{{module_name}}.urls"

TEMPLATES = [
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
     "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug", "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages",
    ]}},
]

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"]}

CORS_ALLOW_ALL_ORIGINS = True
''',
            "{{module_name}}/urls.py": '''"""URL configuration for {{project_name}}."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("health", lambda r: __import__("django.http").HttpResponse('{"status":"ok"}', content_type="application/json")),
]
''',
            "api/__init__.py": "",
            "api/models.py": '''"""API models."""
from django.db import models

class Item(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
''',
            "api/serializers.py": '''"""API serializers."""
from rest_framework import serializers
from .models import Item

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "title", "description", "created_at"]
''',
            "api/urls.py": '''"""API URLs."""
from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"items", views.ItemViewSet)

urlpatterns = router.urls
''',
            "api/views.py": '''"""API views."""
from rest_framework import viewsets
from .models import Item
from .serializers import ItemSerializer

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
''',
            ".gitignore": """__pycache__/
*.py[cod]
*.egg-info/
.env
*.sqlite3
db.sqlite3
static/
""",
        },
        "post_instructions": [
            "Install: `pip install -r requirements.txt`",
            "Migrate: `python manage.py migrate`",
            "Create superuser: `python manage.py createsuperuser`",
            "Run: `python manage.py runserver`",
            "API at http://localhost:8000/api/items/",
        ],
    },
}


def _resolve_name(project_name: str) -> str:
    """Convert project name to a valid Python module name."""
    return re.sub(r'[^a-z0-9]', '_', project_name.lower()).strip('_') or "myproject"


def _expand_template_vars(content: str, variables: Dict[str, str]) -> str:
    """Replace {{var}} placeholders in template content."""
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def list_templates() -> List[Dict[str, str]]:
    """List all available templates (built-in + custom)."""
    templates = []
    for name, tmpl in BUILTIN_TEMPLATES.items():
        templates.append({"name": name, "description": tmpl["description"], "source": "builtin"})
    # Custom templates
    CUSTOM_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(CUSTOM_TEMPLATES_DIR.glob("*.json")):
        try:
            import json
            data = json.loads(path.read_text())
            if isinstance(data, dict) and "files" in data:
                templates.append({
                    "name": path.stem,
                    "description": data.get("description", "Custom template"),
                    "source": "custom",
                })
        except Exception:
            continue
    return templates


def use_template(
    template_name: str,
    output_dir: str,
    project_name: Optional[str] = None,
    description: Optional[str] = None,
    author: Optional[str] = None,
) -> Tuple[int, List[str]]:
    """Generate a project from a template. Returns (file_count, instructions)."""
    import json

    tmpl = BUILTIN_TEMPLATES.get(template_name)
    if not tmpl:
        # Try custom template
        custom_path = CUSTOM_TEMPLATES_DIR / f"{template_name}.json"
        if custom_path.exists():
            try:
                tmpl = json.loads(custom_path.read_text())
            except Exception:
                return 0, [f"Custom template not found: {template_name}"]
        else:
            return 0, [f"Template not found: {template_name}"]

    proj_name = project_name or os.path.basename(output_dir) or "myproject"
    module_name = _resolve_name(proj_name)
    desc = description or f"A {template_name} project"
    auth = author or os.environ.get("USER", os.environ.get("USERNAME", "Author"))
    email = f"{auth.lower().replace(' ', '.')}@example.com"

    variables = {
        "project_name": proj_name,
        "module_name": module_name,
        "description": desc,
        "author": auth,
        "email": email,
    }

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    file_count = 0
    for rel_path, content in tmpl.get("files", {}).items():
        expanded = _expand_template_vars(rel_path, variables)
        expanded_content = _expand_template_vars(content, variables)
        file_path = out_path / expanded
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(expanded_content)
        file_count += 1

    instructions = [_expand_template_vars(inst, variables) for inst in tmpl.get("post_instructions", [])]
    return file_count, instructions


# ── Slash command handlers ─────────────────────────────────────────────


def cmd_template(rest: str, messages, client, console: Console, cwd: str, ctx_files):
    """Handle /template commands."""
    parts = rest.strip().split(maxsplit=2)
    sub = parts[0] if parts else ""
    arg1 = parts[1] if len(parts) > 1 else ""
    arg2 = parts[2] if len(parts) > 2 else ""

    handlers = {
        "list": _template_list,
        "use": _template_use,
    }

    handler = handlers.get(sub)
    if not handler:
        console.print("[error]Usage: /template <list|use> [args][/error]")
        return
    handler(arg1, arg2, messages, client, console, cwd, ctx_files)


def _template_list(_arg1, _arg2, messages, client, console, cwd, ctx_files):
    """List available templates."""
    templates = list_templates()
    if not templates:
        console.print("[system]No templates available.[/system]")
        return

    table = Table(title="📋 Project Templates", border_style="dim")
    table.add_column("Name", style="cyan", min_width=18)
    table.add_column("Source", style="dim", width=10)
    table.add_column("Description", max_width=50)

    for t in templates:
        table.add_row(t["name"], t["source"], t["description"])

    console.print(table)
    console.print("[dim]Use /template use <name> to scaffold a project.[/dim]")


def _template_use(name: str, rest: str, messages, client, console, cwd, ctx_files):
    """Generate a project from a template."""
    if not name:
        console.print("[error]Usage: /template use <name> [output_dir][/error]")
        return

    output_dir = rest.strip() or os.path.join(cwd, name)
    count, instructions = use_template(name, output_dir)

    if count == 0:
        for msg in instructions:
            console.print(f"[error]{msg}[/error]")
        return

    console.print(f"[success]✅ Generated {count} files in: {output_dir}[/success]")
    if instructions:
        console.print("[bold]Next steps:[/bold]")
        for inst in instructions:
            console.print(f"  [info]→ {inst}[/info]")
