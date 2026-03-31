from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.text import slugify

from .models import CompanyData, ReviewDecision, User, UserRole, VendorDocument, VendorProfile


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput())


class AdminUserCreateForm(forms.Form):
    role = forms.ChoiceField(
        choices=[
            (UserRole.VENDOR, "Vendor"),
            (UserRole.PURCHASE, "Purchase"),
            (UserRole.QC, "QA"),
        ]
    )
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    logo = forms.ImageField(required=False)
    barcode = forms.ImageField(required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def build_username(self):
        base = slugify(self.cleaned_data["full_name"]) or self.cleaned_data["email"].split("@")[0]
        candidate = base[:20]
        suffix = 1
        while User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base[:16]}{suffix}"
        return candidate

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        if role != UserRole.VENDOR:
            cleaned_data["logo"] = None
            cleaned_data["barcode"] = None
        return cleaned_data


class CompanyDataForm(forms.ModelForm):
    class Meta:
        model = CompanyData
        fields = ["company_name", "company_address", "signature", "seal"]


class VendorDocumentForm(forms.ModelForm):
    forging_data = forms.JSONField(required=False, widget=forms.HiddenInput())
    chemical_data = forms.JSONField(required=False, widget=forms.HiddenInput())
    mechanical_data = forms.JSONField(required=False, widget=forms.HiddenInput())
    heat_treatment_details = forms.JSONField(required=False, widget=forms.HiddenInput())
    line_items = forms.JSONField(required=False, widget=forms.HiddenInput())

    chemical_columns = [
        ("c", "C"),
        ("si", "Si"),
        ("mn", "Mn"),
        ("p", "P"),
        ("s", "S"),
        ("cr", "Cr"),
        ("mo", "Mo"),
        ("ni", "Ni"),
        ("cu", "Cu"),
        ("v", "V"),
        ("nb", "Nb"),
        ("cr_mo", "Cr+Mo"),
        ("cr_mo_ni_cu_v", "Cr+Mo+Ni+Cu+V"),
        ("ce", "CE"),
    ]

    chemical_rows = [
        ("min", "Min"),
        ("max", "Max"),
        ("actual", "Actual"),
    ]

    mechanical_rows = [
        ("yield_strength", "0.2% Proof Stress (MPa)"),
        ("tensile_strength", "UTS (MPa)"),
        ("elongation", "%EL GL=2"),
        ("reduction_of_area", "% Reduction of Area"),
    ]

    line_item_indices = range(5)
    heat_row_indices = range(4)

    class Meta:
        model = VendorDocument
        fields = [
            "document_number",
            "company_name",
            "company_address",
            "barcode_value",
            "certificate_date",
            "customer_name",
            "customer_email",
            "po_number",
            "material_grade",
            "material_standard",
            "tdc_number",
            "maker",
            "mill_certificate_number",
            "raw_material_specification",
            "raw_material_standard",
            "manufacturing_process",
            "heat_number",
            "forging_data",
            "chemical_data",
            "mechanical_data",
            "heat_treatment_details",
            "line_items",
            "notes",
            "authorized_signatory",
            "signatory_role",
        ]
        widgets = {
            "certificate_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["document_number"].label = "TC No"
        self.fields["company_name"].label = "Company Name"
        self.fields["company_address"].label = "Company Address"
        self.fields["barcode_value"].label = "Barcode"
        self.fields["certificate_date"].label = "Date"
        self.fields["po_number"].label = "P.O. No. / Date"
        self.fields["raw_material_specification"].label = "RM Specifications"
        self.fields["raw_material_standard"].label = "Specification / Standard"
        self.fields["manufacturing_process"].label = "Mfg Process"

        forging_data = self.instance.forging_data if self.instance and self.instance.pk else {}
        chemical_data = self.instance.chemical_data if self.instance and self.instance.pk else {}
        mechanical_data = self.instance.mechanical_data if self.instance and self.instance.pk else {}
        heat_treatment = self.instance.heat_treatment_details if self.instance and self.instance.pk else {}
        line_items = self.instance.line_items if self.instance and self.instance.pk else []

        self._add_text_field("forging_heat_no", "Heat No", forging_data.get("heat_no", ""))
        self._add_text_field("forging_heat_batch_no", "Heat Batch No", forging_data.get("heat_batch_no", ""))
        self._add_text_field("forging_forge_method", "Forge Method", forging_data.get("forge_method", ""))
        self._add_text_field(
            "forging_supplier_identification",
            "Supplier Identification",
            forging_data.get("supplier_identification", ""),
        )

        for row_key, row_label in self.chemical_rows:
            for column_key, column_label in self.chemical_columns:
                initial = self._lookup_nested(chemical_data, column_key, row_key)
                self._add_text_field(
                    f"chemical_{row_key}_{column_key}",
                    f"{row_label} {column_label}",
                    initial,
                )

        for row_key, row_label in self.mechanical_rows:
            self._add_text_field(
                f"mechanical_spec_min_{row_key}",
                f"{row_label} Spec Min",
                self._lookup_nested(mechanical_data, row_key, "spec_min"),
            )
            self._add_text_field(
                f"mechanical_spec_max_{row_key}",
                f"{row_label} Spec Max",
                self._lookup_nested(mechanical_data, row_key, "spec_max"),
            )
            self._add_text_field(
                f"mechanical_actual_{row_key}",
                f"{row_label} Actual",
                self._lookup_nested(mechanical_data, row_key, "actual"),
            )

        hardness_data = mechanical_data.get("hardness_hbv", {})
        self._add_text_field(
            "mechanical_hardness_spec_max",
            "Hardness HBW Spec Max",
            hardness_data.get("spec_max", ""),
        )
        hardness_actuals = hardness_data.get("actual_values", ["", "", ""])
        for index in range(3):
            initial = hardness_actuals[index] if index < len(hardness_actuals) else ""
            self._add_text_field(f"mechanical_hardness_actual_{index}", f"Hardness Actual {index + 1}", initial)

        impact_data = mechanical_data.get("impact_test", {})
        self._add_text_field(
            "mechanical_impact_specimen_size",
            "Impact Specimen Size",
            impact_data.get("specimen_size", "10*10*55mm"),
        )
        self._add_text_field(
            "mechanical_impact_temperature",
            "Impact Test Temperature",
            impact_data.get("test_temperature", "-46 C"),
        )
        self._add_text_field(
            "mechanical_impact_single_min",
            "Impact Single Min",
            impact_data.get("single_min", ""),
        )
        self._add_text_field(
            "mechanical_impact_average_min",
            "Impact Average Min",
            impact_data.get("average_min", ""),
        )
        impact_actuals = impact_data.get("actual_values", ["", "", ""])
        for index in range(3):
            initial = impact_actuals[index] if index < len(impact_actuals) else ""
            self._add_text_field(f"mechanical_impact_actual_{index}", f"Impact Actual {index + 1}", initial)
        self._add_text_field(
            "mechanical_impact_low_temp_actual",
            "Impact Low Temperature Actual",
            impact_data.get("low_temp_actual", ""),
        )

        self._add_text_field("heat_process", "Heat Treatment Process", heat_treatment.get("process", ""))
        self._add_text_field("heat_header_no", "Heat No", heat_treatment.get("heat_no", ""))
        self._add_text_field("heat_batch_no", "Heat Batch No", heat_treatment.get("heat_batch_no", ""))
        self._add_text_field("heat_furnace_type", "Furnace Type", heat_treatment.get("furnace_type", ""))
        self._add_text_field("heat_furnace_no", "HT Furnace No", heat_treatment.get("furnace_no", ""))

        heat_rows = heat_treatment.get("rows", [])
        for index in self.heat_row_indices:
            row = heat_rows[index] if index < len(heat_rows) else {}
            self._add_text_field(f"heat_row_{index}_temperature", "Temperature", row.get("temperature_c", ""))
            self._add_text_field(f"heat_row_{index}_hours", "Soaking Time", row.get("soaking_hours", ""))
            self._add_text_field(f"heat_row_{index}_cooling", "Cooling Medium", row.get("cooling_medium", ""))

        for index in self.line_item_indices:
            row = line_items[index] if index < len(line_items) else {}
            self._add_text_field(f"line_item_{index}_item", "Item", row.get("item", ""))
            self._add_text_field(f"line_item_{index}_description", "Description", row.get("description", ""))
            self._add_text_field(f"line_item_{index}_specification", "Specification", row.get("specification", ""))
            self._add_text_field(f"line_item_{index}_production_no", "Production No", row.get("production_no", ""))
            self._add_text_field(f"line_item_{index}_total_quantity", "Total Qty", row.get("total_quantity", ""))
            self._add_text_field(f"line_item_{index}_supplied_quantity", "Supplied Qty", row.get("supplied_quantity", ""))

    def _add_text_field(self, name, label, initial=""):
        self.fields[name] = forms.CharField(required=False, label=label, initial=initial)

    def _lookup_nested(self, data, key, nested_key):
        value = data.get(key, "")
        if isinstance(value, dict):
            return value.get(nested_key, "")
        return ""

    def clean(self):
        cleaned_data = super().clean()

        cleaned_data["forging_data"] = {
            "heat_no": cleaned_data.get("forging_heat_no", "").strip(),
            "heat_batch_no": cleaned_data.get("forging_heat_batch_no", "").strip(),
            "forge_method": cleaned_data.get("forging_forge_method", "").strip(),
            "supplier_identification": cleaned_data.get("forging_supplier_identification", "").strip(),
        }

        cleaned_data["chemical_data"] = {
            column_key: {
                row_key: cleaned_data.get(f"chemical_{row_key}_{column_key}", "").strip()
                for row_key, _ in self.chemical_rows
            }
            for column_key, _ in self.chemical_columns
        }

        cleaned_data["mechanical_data"] = {
            row_key: {
                "spec_min": cleaned_data.get(f"mechanical_spec_min_{row_key}", "").strip(),
                "spec_max": cleaned_data.get(f"mechanical_spec_max_{row_key}", "").strip(),
                "actual": cleaned_data.get(f"mechanical_actual_{row_key}", "").strip(),
            }
            for row_key, _ in self.mechanical_rows
        }
        cleaned_data["mechanical_data"]["hardness_hbv"] = {
            "spec_min": "",
            "spec_max": cleaned_data.get("mechanical_hardness_spec_max", "").strip(),
            "actual_values": [
                cleaned_data.get(f"mechanical_hardness_actual_{index}", "").strip()
                for index in range(3)
            ],
        }
        cleaned_data["mechanical_data"]["impact_test"] = {
            "specimen_size": cleaned_data.get("mechanical_impact_specimen_size", "").strip(),
            "test_temperature": cleaned_data.get("mechanical_impact_temperature", "").strip(),
            "single_min": cleaned_data.get("mechanical_impact_single_min", "").strip(),
            "average_min": cleaned_data.get("mechanical_impact_average_min", "").strip(),
            "actual_values": [
                cleaned_data.get(f"mechanical_impact_actual_{index}", "").strip()
                for index in range(3)
            ],
            "low_temp_actual": cleaned_data.get("mechanical_impact_low_temp_actual", "").strip(),
        }

        cleaned_data["heat_treatment_details"] = {
            "heat_no": cleaned_data.get("heat_header_no", "").strip(),
            "heat_batch_no": cleaned_data.get("heat_batch_no", "").strip(),
            "process": cleaned_data.get("heat_process", "").strip(),
            "furnace_type": cleaned_data.get("heat_furnace_type", "").strip(),
            "furnace_no": cleaned_data.get("heat_furnace_no", "").strip(),
            "rows": [
                {
                    "temperature_c": cleaned_data.get(f"heat_row_{index}_temperature", "").strip(),
                    "soaking_hours": cleaned_data.get(f"heat_row_{index}_hours", "").strip(),
                    "cooling_medium": cleaned_data.get(f"heat_row_{index}_cooling", "").strip(),
                }
                for index in self.heat_row_indices
            ],
        }

        cleaned_data["line_items"] = [
            {
                "item": cleaned_data.get(f"line_item_{index}_item", "").strip(),
                "description": cleaned_data.get(f"line_item_{index}_description", "").strip(),
                "specification": cleaned_data.get(f"line_item_{index}_specification", "").strip(),
                "production_no": cleaned_data.get(f"line_item_{index}_production_no", "").strip(),
                "total_quantity": cleaned_data.get(f"line_item_{index}_total_quantity", "").strip(),
                "supplied_quantity": cleaned_data.get(f"line_item_{index}_supplied_quantity", "").strip(),
            }
            for index in self.line_item_indices
        ]

        required_fields = {
            "document_number": "TC number is required.",
            "customer_name": "Customer name is required.",
            "certificate_date": "Certificate date is required.",
        }
        for field_name, message in required_fields.items():
            if not cleaned_data.get(field_name):
                self.add_error(field_name, message)

        return cleaned_data


class ReviewActionForm(forms.Form):
    decision = forms.ChoiceField(choices=ReviewDecision.choices)
    comments = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def clean_comments(self):
        comments = self.cleaned_data["comments"].strip()
        if len(comments) < 5:
            raise forms.ValidationError("Please add a meaningful review comment.")
        return comments
