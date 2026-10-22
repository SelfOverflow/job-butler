"""Technology vocabulary and skill detection for market analytics.

The vocabulary is generic (no candidate data). Each line is `Canonical: alias, ...`;
an alias starting with `=` is matched case-sensitively as written (for words like
"Go" that are common in prose). When matches overlap, the longest wins, so
"React Native" does not also count "React".
"""

from functools import cache

from src.ingestion.base import words
from src.profile.models import CandidateProfile

_VOCABULARY = """
Python: python
Java: java
JavaScript: javascript, js, ecmascript
TypeScript: typescript, ts
Go: golang, =Go
Rust: rust
C++: c++, cpp
C#: c#, csharp, .net core
Kotlin: kotlin
Swift: swift
Scala: scala
Ruby: ruby
Ruby on Rails: ruby on rails, rails
PHP: php
Elixir: elixir
React: react, react.js, reactjs
React Native: react native
Next.js: next.js, nextjs
Vue: vue, vue.js, vuejs
Angular: angular
Svelte: svelte
Redux: redux
Tailwind CSS: tailwind, tailwind css
GraphQL: graphql
REST APIs: rest api, rest apis, restful
gRPC: grpc
WebSockets: websocket, websockets, socket.io
Node.js: node, node.js, nodejs
Express.js: express, express.js
NestJS: nestjs
Django: django
Flask: flask
FastAPI: fastapi
Spring Boot: spring boot, spring
Expo: expo
Flutter: flutter
Android: android
iOS: ios
AWS: aws, amazon web services
AWS Lambda: aws lambda, lambda
Amazon S3: s3
Amazon ECS: ecs
Amazon EKS: eks
GCP: gcp, google cloud
Azure: azure
Docker: docker, containers
Kubernetes: kubernetes, k8s
Helm: helm
Terraform: terraform
Ansible: ansible
Pulumi: pulumi
CI/CD: ci/cd, ci cd, continuous integration
GitHub Actions: github actions
Jenkins: jenkins
ArgoCD: argocd, argo cd
Linux: linux
PostgreSQL: postgresql, postgres
MySQL: mysql
MongoDB: mongodb, mongo
Redis: redis
Elasticsearch: elasticsearch, opensearch
Cassandra: cassandra
DynamoDB: dynamodb
SQLite: sqlite
Snowflake: snowflake
BigQuery: bigquery
Kafka: kafka
RabbitMQ: rabbitmq
Spark: spark, pyspark
Airflow: airflow
dbt: dbt
Microservices: microservices, microservice
Distributed Systems: distributed systems
System Design: system design
Prometheus: prometheus
Grafana: grafana
Datadog: datadog
OpenTelemetry: opentelemetry
Machine Learning: machine learning, ml
LLMs: llm, llms, large language models
PyTorch: pytorch
TensorFlow: tensorflow
LangChain: langchain
Pandas: pandas
Selenium: selenium
Playwright: playwright
Cypress: cypress
Jest: jest
Pytest: pytest
TDD: tdd, test-driven development
OAuth: oauth, oauth2
Auth0: auth0
Webpack: webpack
Vite: vite
Turborepo: turborepo
Figma: figma
"""


@cache
def _index() -> tuple[dict[str, list[tuple[tuple[str, ...], str]]], dict[str, str]]:
    """Word aliases keyed by first word (longest first), and case-sensitive literals."""
    by_first: dict[str, list[tuple[tuple[str, ...], str]]] = {}
    literals: dict[str, str] = {}
    for line in _VOCABULARY.strip().splitlines():
        canonical, _, raw = line.partition(":")
        for alias in (a.strip() for a in raw.split(",")):
            if alias.startswith("="):
                literals[alias[1:]] = canonical
            elif tokens := words(alias):
                by_first.setdefault(tokens[0], []).append((tokens, canonical))
    for entries in by_first.values():
        entries.sort(key=lambda e: -len(e[0]))
    return by_first, literals


def mentioned_skills(text: str) -> set[str]:
    """Canonical technologies named in `text`; at each position the longest alias wins.

    A single left-to-right scan: matched spans are skipped, so "React Native" never
    also counts "React".
    """
    by_first, literals = _index()
    found = {literals[t] for t in (raw.strip(".,;:()") for raw in text.split()) if t in literals}
    tokens, i = words(text), 0
    while i < len(tokens):
        for alias, canonical in by_first.get(tokens[i], ()):
            if tokens[i : i + len(alias)] == alias:
                found.add(canonical)
                i += len(alias) - 1
                break
        i += 1
    return found


def candidate_skills(profile: CandidateProfile) -> set[str]:
    """Technologies the candidate has: inventory names (incl. parentheticals) and bullet tags."""
    names = [s.name for group in profile.skills_inventory.values() for s in group]
    names += [tag for bullet in profile.bullets for tag in bullet.skills]
    return set().union(*(mentioned_skills(name) for name in names)) if names else set()
