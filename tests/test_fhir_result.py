from ncpi_fhir_client.fhir_result import FhirResult


def make_payload(response, status_code=200):
    return {"status_code": status_code, "request_url": "http://x", "response": response}


class TestEntries:
    def test_empty_bundle_with_zero_total_has_no_entries(self):
        result = FhirResult(make_payload({"total": 0}))
        assert result.entries == []
        assert result.entry_count == 0

    def test_bundle_with_entry_list(self):
        entries = [{"resource": {"id": "1"}}, {"resource": {"id": "2"}}]
        result = FhirResult(make_payload({"entry": entries}))
        assert result.entries == entries
        assert result.entry_count == 2

    def test_response_without_entry_key_is_wrapped_as_a_single_entry(self):
        response = {"issue": ["bad"]}
        result = FhirResult(make_payload(response, status_code=404))
        assert result.entries == [response]


class TestSuccess:
    def test_2xx_status_is_successful(self):
        result = FhirResult(make_payload({"total": 0}, status_code=200))
        assert result.success() is True

    def test_non_2xx_status_is_not_successful(self):
        result = FhirResult(make_payload({"issue": []}, status_code=404))
        assert result.success() is False


class TestPagination:
    def test_next_link_is_captured(self):
        response = {
            "entry": [{"a": 1}],
            "link": [{"relation": "next", "url": "http://x/page2"}],
        }
        result = FhirResult(make_payload(response))
        assert result.next == "http://x/page2"

    def test_next_is_none_without_a_next_link(self):
        response = {"entry": [{"a": 1}], "link": [{"relation": "self", "url": "http://x"}]}
        result = FhirResult(make_payload(response))
        assert result.next is None

    def test_append_extends_entries_and_updates_next(self):
        result = FhirResult(
            make_payload(
                {
                    "entry": [{"a": 1}],
                    "link": [{"relation": "next", "url": "http://x/page2"}],
                }
            )
        )

        result.append(
            {
                "response": {
                    "entry": [{"b": 2}],
                    "link": [{"relation": "self", "url": "http://x/page2"}],
                }
            }
        )

        assert result.entries == [{"a": 1}, {"b": 2}]
        assert result.entry_count == 2
        assert result.next is None
