import pulumi
import pulumi_keycloak as keycloak

from config import config
from keycloak_iam.provider import master_provider

main_realm = keycloak.Realm(
    resource_name=config.realm_name,
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm=config.realm_name,
    enabled=True,
    display_name=config.realm_display_name,
    display_name_html=f"<b>{config.realm_display_name}</b>",
    login_theme="keycloak",
    access_code_lifespan="1h",
    ssl_required="external",
    user_managed_access=True,
    registration_allowed=True,
    registration_email_as_username=True,
    remember_me=True,
    reset_password_allowed=True,
    verify_email=True,
    login_with_email_allowed=True,
    duplicate_emails_allowed=False,
    edit_username_allowed=False,
    password_policy="upperCase(1) and length(8) and forceExpiredPasswordChange(365) and notUsername",  # noqa: S106 Possible hardcoded password assigned to argument
    # TODO: Add SMTP server
    # smtp_server={
    #     "host": "smtp.example.com",
    #     "from_": "example@example.com",
    #     "auth": {
    #         "username": "TBD",
    #         "password": "TBD",
    #     },
    # },
    internationalization={
        "supported_locales": [
            "en",
            "pl",
        ],
        "default_locale": "en",
    },
    security_defenses={
        "headers": {
            "x_frame_options": "DENY",
            "content_security_policy": "frame-src 'self'; frame-ancestors 'self'; object-src 'none';",
            "content_security_policy_report_only": "",
            "x_content_type_options": "nosniff",
            "x_robots_tag": "none",
            "x_xss_protection": "1; mode=block",
            "strict_transport_security": "max-age=31536000; includeSubDomains",
        },
        "brute_force_detection": {
            "permanent_lockout": False,
            "max_login_failures": 30,
            "wait_increment_seconds": 60,
            "quick_login_check_milli_seconds": 1000,
            "minimum_quick_login_wait_seconds": 60,
            "max_failure_wait_seconds": 900,
            "failure_reset_time_seconds": 43200,
        },
    },
)

# Update user profile for realm
user_profile = keycloak.RealmUserProfile(
    resource_name="user-profile",
    opts=pulumi.ResourceOptions(provider=master_provider),
    realm_id=main_realm.realm,
    attributes=[
        {
            "name": "username",
            "displayName": "${username}",
            "validators": [{"name": "length", "config": {"min": "3", "max": "255"}}],
            "requiredForRoles": ["user"],
            "permissions": {
                "view": [
                    "admin",
                    "user",
                ],
                "edit": [
                    "admin",
                    "user",
                ],
            },
        },
        {
            "name": "email",
            "displayName": "${email}",
            "validators": [
                {
                    "name": "length",
                    "config": {
                        "min": "3",
                        "max": "255",
                    },
                },
            ],
            "requiredForRoles": ["user"],
            "permissions": {
                "view": [
                    "admin",
                    "user",
                ],
                "edit": [
                    "admin",
                    "user",
                ],
            },
        },
    ],
)
