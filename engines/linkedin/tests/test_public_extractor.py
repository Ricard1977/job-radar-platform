from pathlib import Path
import sys

ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_DIR))

from core.public_extractor import extract_job_id


def test_extracts_job_id_from_slugged_url():
    url = "https://www.linkedin.com/jobs/view/project-manager-at-example-4470487203?position=1"
    assert extract_job_id(url) == "4470487203"


def test_extracts_job_id_from_plain_url():
    url = "https://www.linkedin.com/jobs/view/4470487203"
    assert extract_job_id(url) == "4470487203"
