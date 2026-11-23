app_name = "battery_track"
app_title = "Battery Track"
app_publisher = "Mayank Ahuja"
app_description = "Serial-number traceability for battery packs: stock in, build, scan, dispatch, trace"
app_email = "mayankahuja785@gmail.com"
app_license = "mit"

# Apps
# ------------------

# ERPNext must be installed first: our custom field and hooks use Sales Order, Stock Entry, Delivery Note.
# (frappe is always there; QR codes use pyqrcode, which ships with frappe, so no extra app is needed)
required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "battery_track",
# 		"logo": "/assets/battery_track/logo.png",
# 		"title": "Battery Track",
# 		"route": "/battery_track",
# 		"has_permission": "battery_track.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/battery_track/css/battery_track.css"
# app_include_js = "/assets/battery_track/js/battery_track.js"

# include js, css files in header of web template
# web_include_css = "/assets/battery_track/css/battery_track.css"
# web_include_js = "/assets/battery_track/js/battery_track.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "battery_track/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# Work Order form: "Build Packs" button (one click, one Manufacture entry per pack)
doctype_js = {"Work Order": "public/js/work_order.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "battery_track/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "battery_track.utils.jinja_methods",
# 	"filters": "battery_track.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "battery_track.install.before_install"
# after_install = "battery_track.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "battery_track.uninstall.before_uninstall"
# after_uninstall = "battery_track.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "battery_track.utils.before_app_install"
# after_app_install = "battery_track.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "battery_track.utils.before_app_uninstall"
# after_app_uninstall = "battery_track.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "battery_track.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "battery_track.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "battery_track.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["battery_track.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Functions print formats can call, e.g. {{ qr_code_data_uri(doc.name) }}
jinja = {
	"methods": ["battery_track.jinja_helpers.qr_code_data_uri"],
}

# Fixtures: custom fields we add to ERPNext doctypes are exported into the app
# (battery_track/fixtures/custom_field.json) and re-created on any site where the app is installed.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "=", "Battery Track"]]},
	# workspace hero banner (Custom HTML Block has no "module" field, so it can't be exported as standard)
	{"dt": "Custom HTML Block", "filters": [["name", "=", "Battery Track Hero"]]},
]

doc_events = {
	# Pack traceability: runs after ERPNext's own Stock Entry logic
	"Stock Entry": {
		"before_submit": "battery_track.events.stock_entry.before_submit",
		"on_submit": "battery_track.events.stock_entry.on_submit",
		"on_cancel": "battery_track.events.stock_entry.on_cancel",
	},
	# Dispatch rule: only scanned packs can be delivered
	"Delivery Note": {
		"before_validate": "battery_track.events.delivery_note.before_validate",
		"before_submit": "battery_track.events.delivery_note.before_submit",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"battery_track.tasks.all"
# 	],
# 	"daily": [
# 		"battery_track.tasks.daily"
# 	],
# 	"hourly": [
# 		"battery_track.tasks.hourly"
# 	],
# 	"weekly": [
# 		"battery_track.tasks.weekly"
# 	],
# 	"monthly": [
# 		"battery_track.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "battery_track.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "battery_track.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "battery_track.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["battery_track.utils.before_request"]
# after_request = ["battery_track.utils.after_request"]

# Job Events
# ----------
# before_job = ["battery_track.utils.before_job"]
# after_job = ["battery_track.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"battery_track.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

