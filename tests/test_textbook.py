from pensionlab.lab import textbook
from pensionlab.lab.topics import TOPICS


def test_every_topic_has_textbook_sections():
    assert set(textbook.TOPIC_SECTIONS) == set(TOPICS)
    for t in TOPICS:
        r = textbook.refs(t)
        assert r and all(url.startswith(textbook.URL + "#page=") for _, _, url in r)


def test_page_offset_and_alias():
    title, page, url = textbook.refs("財政方式（Trowbridgeモデル）")[0]
    assert page == 52 and url.endswith("#page=65")
    assert textbook.refs("life_annuity")[0][0].startswith("理論編 第2章")     # legacy sample topic
