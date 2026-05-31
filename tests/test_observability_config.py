from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_promtail_uses_docker_discovery_and_json_labels():
    config = yaml.safe_load((ROOT / "observability/promtail/config.yml").read_text())
    scrape_config = config["scrape_configs"][0]
    stages = scrape_config["pipeline_stages"]

    assert scrape_config["job_name"] == "docker-containers"
    assert scrape_config["docker_sd_configs"][0]["host"] == "unix:///var/run/docker.sock"
    assert any("docker" in stage for stage in stages)
    assert any(stage.get("json", {}).get("expressions", {}).get("event") == "event" for stage in stages)
    assert any("labels" in stage and "tenant_id" in stage["labels"] for stage in stages)


def test_grafana_loki_datasource_has_stable_uid():
    config = yaml.safe_load((ROOT / "observability/grafana/datasources/loki.yml").read_text())
    datasource = config["datasources"][0]

    assert datasource["name"] == "Loki"
    assert datasource["uid"] == "loki"
    assert datasource["url"] == "http://loki:3100"


def test_dashboards_are_valid_json_and_reference_loki():
    dashboard_dir = ROOT / "observability/grafana/dashboards"
    dashboards = sorted(dashboard_dir.glob("*.json"))

    assert {dashboard.name for dashboard in dashboards} == {
        "api-traffic.json",
        "security-events.json",
        "tenant-activity.json",
    }
    for dashboard_path in dashboards:
        dashboard = json.loads(dashboard_path.read_text())
        assert dashboard["uid"].startswith("nt219-")
        assert dashboard["panels"]
        assert '"uid": "loki"' in dashboard_path.read_text()


def test_security_alerts_cover_required_events():
    config = yaml.safe_load((ROOT / "observability/grafana/alerts/security-alerts.yaml").read_text())
    titles = {rule["title"] for group in config["groups"] for rule in group["rules"]}

    assert titles == {
        "HighAuthFailureRate",
        "BOLAAttemptDetected",
        "RateLimitViolation",
        "StripeWebhookFailure",
    }


def test_observability_files_do_not_embed_secrets():
    observability_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "observability").rglob("*")
        if path.is_file() and path.suffix in {".yml", ".yaml", ".json"}
    )

    forbidden = ["Authorization: Bearer", "access_token", "refresh_token", "client_secret", "VAULT_TOKEN", "private_key"]
    for value in forbidden:
        assert value not in observability_text
