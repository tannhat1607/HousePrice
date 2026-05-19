from django.test import TestCase


class PredictorViewTests(TestCase):
    def test_index_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
