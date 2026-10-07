import csv
from types import SimpleNamespace

import pytest

from fb_leads import __main__ as cli
from fb_leads import apify_source
from fb_leads.leads import has_contact, normalize_page_url, to_lead


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.facebook.com/SmileDentalMiami/", "https://www.facebook.com/SmileDentalMiami"),
        ("https://m.facebook.com/SmileDentalMiami/posts/123", "https://www.facebook.com/SmileDentalMiami"),
        ("https://www.facebook.com/SmileDentalMiami/about?ref=x", "https://www.facebook.com/SmileDentalMiami"),
        ("https://www.facebook.com/profile.php?id=100064&sk=about", "https://www.facebook.com/profile.php?id=100064"),
        ("https://www.facebook.com/people/Joe-Plumbing/100083/", "https://www.facebook.com/people/Joe-Plumbing/100083"),
        ("https://www.facebook.com/pg/AcmeRoofing/reviews/", "https://www.facebook.com/AcmeRoofing"),
        ("https://www.facebook.com/groups/miamibiz/", None),
        ("https://www.facebook.com/events/555/", None),
        ("https://www.facebook.com/", None),
        ("https://www.instagram.com/acme", None),
        ("https://notfacebook.com/acme", None),
    ],
)
def test_normalize_page_url(url, expected):
    assert normalize_page_url(url) == expected


def test_to_lead_maps_fields_and_finds_email_in_text():
    lead = to_lead({
        "facebookUrl": "https://www.facebook.com/SmileDentalMiami",
        "title": "Smile Dental",
        "categories": ["Dentist", "Health"],
        "phone": "+1 305-555-0100",
        "websites": ["https://smile.example"],
        "info": ["Call us or email hello@smile.example today"],
        "likes": 1200,
    })
    assert lead["name"] == "Smile Dental"
    assert lead["category"] == "Dentist, Health"
    assert lead["email"] == "hello@smile.example"
    assert lead["website"] == "https://smile.example"
    assert lead["likes"] == "1200"
    assert has_contact(lead)


def test_to_lead_without_contact():
    assert not has_contact(to_lead({"facebookUrl": "https://www.facebook.com/x", "title": "X"}))


class FakeActor:
    def __init__(self, store, actor_id):
        self.store, self.actor_id = store, actor_id

    def call(self, run_input):
        self.store.calls.append((self.actor_id, run_input))
        return SimpleNamespace(status="SUCCEEDED", default_dataset_id=self.actor_id)


class FakeClient:
    def __init__(self, token):
        self.calls = []
        self.datasets = {
            apify_source.SEARCH_ACTOR: [{
                "searchQuery": {"term": "site:facebook.com dentist Miami"},
                "organicResults": [
                    {"url": "https://www.facebook.com/SmileDentalMiami/"},
                    {"url": "https://m.facebook.com/SmileDentalMiami/posts/1"},
                    {"url": "https://www.facebook.com/groups/miami"},
                    {"url": "https://www.facebook.com/NoContactDental"},
                ],
            }],
            apify_source.PAGES_ACTOR: [
                {"facebookUrl": "https://www.facebook.com/SmileDentalMiami", "title": "Smile", "email": "a@smile.example"},
                {"facebookUrl": "https://www.facebook.com/NoContactDental", "title": "Quiet"},
            ],
        }

    def actor(self, actor_id):
        return FakeActor(self, actor_id)

    def dataset(self, dataset_id):
        return SimpleNamespace(iterate_items=lambda: iter(self.datasets[dataset_id]))


def test_end_to_end_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test")
    holder = {}
    monkeypatch.setattr("apify_client.ApifyClient", lambda t: holder.setdefault("c", FakeClient(t)))
    out = tmp_path / "leads.csv"

    assert cli.main(["-k", "dentist", "-l", "Miami", "--no-sheet", "--csv", str(out)]) == 0

    search_call, pages_call = holder["c"].calls
    assert search_call[1]["queries"] == "site:facebook.com dentist Miami"
    assert [s["url"] for s in pages_call[1]["startUrls"]] == [
        "https://www.facebook.com/SmileDentalMiami",
        "https://www.facebook.com/NoContactDental",
    ]
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 1
    assert rows[0]["email"] == "a@smile.example"
    assert rows[0]["search_query"] == "dentist Miami"
