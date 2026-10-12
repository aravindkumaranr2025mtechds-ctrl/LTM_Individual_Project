import unittest

from pydantic import ValidationError

from app.main import (
    TroubleshootingRequest,
    app,
)


class TroubleshootOpenAPISchemaTests(
    unittest.TestCase
):
    def test_openapi_exposes_mode_discriminator(self):
        schema = app.openapi()

        field = (
            schema["components"]
            ["schemas"]
            ["TroubleshootingRequest"]
            ["properties"]
            ["structured_assistance"]
        )

        variants = [
            item
            for item in field["anyOf"]
            if "oneOf" in item
        ]

        self.assertEqual(
            len(variants),
            1,
        )

        variant = variants[0]

        discriminator = variant[
            "discriminator"
        ]

        self.assertEqual(
            discriminator["propertyName"],
            "mode",
        )

        self.assertEqual(
            set(
                discriminator[
                    "mapping"
                ].keys()
            ),
            {
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            },
        )

        self.assertEqual(
            len(variant["oneOf"]),
            3,
        )

    def test_structured_payload_is_typed(self):
        request = (
            TroubleshootingRequest.model_validate({
                "machine_name": "Siemens",
                "error_code": "61352",
                "symptom": "Need logfile path",
                "structured_assistance": {
                    "mode": "siemens_logfile",
                    "payload": {
                        "alarm_scope":
                            "61352_or_61353",
                    },
                },
            })
        )

        self.assertEqual(
            type(
                request.structured_assistance
            ).__name__,
            "SiemensLogfileOrchestratorRequest",
        )

        self.assertEqual(
            request.structured_assistance.mode,
            "siemens_logfile",
        )

    def test_invalid_mode_rejected_by_request_model(self):
        with self.assertRaises(
            ValidationError
        ):
            TroubleshootingRequest.model_validate({
                "machine_name": "Example",
                "symptom": "Example",
                "structured_assistance": {
                    "mode": "guessed_policy",
                    "payload": {},
                },
            })


if __name__ == "__main__":
    unittest.main()
