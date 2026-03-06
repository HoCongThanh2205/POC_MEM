from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_page, name="login-page"),
    path("register/", views.register_page, name="register-page"),
    path("logout/", views.logout_view, name="logout-page"),
    path("", views.asset_list_page, name="asset-list-page"),
    path("assets/new/", views.create_asset_page, name="asset-create-page"),
    path("assets/<int:asset_id>/edit/", views.edit_asset_page, name="asset-edit-page"),
    path("assets/<int:asset_id>/", views.asset_detail_page, name="asset-detail-page"),
    path("api/master-data/", views.master_data_api, name="master-data-api"),
    path("api/assets/", views.asset_list_api, name="asset-list-api"),
    path("api/assets/create/", views.create_asset_api, name="asset-create-api"),
    path("api/assets/<int:asset_id>/update/", views.update_asset_api, name="asset-update-api"),
    path("api/assets/disable/", views.disable_assets_api, name="disable-assets-api"),
    path("api/assets/<int:asset_id>/", views.asset_detail_api, name="asset-detail-api"),
]
