"""volume URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView, RedirectView

from . import views
from .models import Group, group_type_name


urlpatterns = [
    path('admin/', admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),

    path("", views.chart_view, name="home"),
    path("slopes/", views.chart_view, name="slopes", kwargs={"is_slope": True}),
    path("auth", views.auth),

    path("system/", TemplateView.as_view(template_name="system.html"), name="system"),
    path("system/live-updates-start", views.live_updates_start, name="live-updates-start"),
    path("system/live-updates-pause", views.live_updates_pause, name="live-updates-pause"),
    path("system/api-test", views.api_test, name="api-test"),

    # Charts
    path('charts/', views.ChartsView.as_view(), name="charts"),
    path('charts/add/', views.add_chart, name="add-chart"),
    path('chart/<slug:slug>/', views.chart_view, name="chart"),
    path('chart/<slug:slug>/edit', views.ChartEditView.as_view(), name="chart-edit"),
    path('chart/<slug:slug>/update', views.update_chart, name="chart-update"),
    path('chart/<slug:slug>/delete', views.delete_chart, name="chart-delete"),
    path('chart/<slug:slug>/rename', views.rename_chart, name="chart-rename"),
    path('chart/<slug:slug>/change-data-type', views.change_chart_type, name="chart-change-type"),

    # Indices
    path('indices/', views.IndicesView.as_view(), name="indices"),
    path("index/<str:symbol>/", RedirectView.as_view(pattern_name="index-volume"), name="index-view"),
    path("index/<str:symbol>/volume", RedirectView.as_view(pattern_name="index-volume")),
    path("index/<str:symbol>/volume/", views.stock_view, name="index-volume"),
    path("index/<str:symbol>/slope", RedirectView.as_view(pattern_name="index-slope")),
    path("index/<str:symbol>/slope/", views.stock_view_slope, name="index-slope"),
    path("index/<str:symbol>/correlations-volume", RedirectView.as_view(pattern_name="index-correlations-volume")),
    path("index/<str:symbol>/correlations-volume/", views.rolling_correlation_volume, name="index-correlations-volume"),
    path("index/<str:symbol>/correlations-slope/", views.rolling_correlation_slope, name="index-correlations-slope"),
    path("index/<str:symbol>/correlations-price", RedirectView.as_view(pattern_name="index-correlations-price")),
    path("index/<str:symbol>/correlations-price/", views.rolling_correlation_price, name="index-correlations-price"),
    path("index/<str:symbol>/historical", views.IndexView.as_view(), name="index-historical"),
    path("index/<str:symbol>/weights", views.WeightsView.as_view(), name="index-weights"),

    # Stock
    path('stocks/', views.StocksView.as_view(), name="stocks"),
    path('stocks/add/', views.add_stock, name="add-stock"),
    path("stock/<str:symbol>/", RedirectView.as_view(pattern_name="stock-volume"), name="stock-view"),
    path("stock/<str:symbol>/volume", RedirectView.as_view(pattern_name="stock-volume")),
    path("stock/<str:symbol>/volume/", views.stock_view, name="stock-volume"),
    path("stock/<str:symbol>/slope", RedirectView.as_view(pattern_name="stock-slope")),
    path("stock/<str:symbol>/slope/", views.stock_view_slope, name="stock-slope"),
    path("stock/<str:symbol>/correlations-volume", RedirectView.as_view(pattern_name="stock-correlations-volume")),
    path("stock/<str:symbol>/correlations-volume/", views.rolling_correlation_volume, name="stock-correlations-volume"),
    path("stock/<str:symbol>/correlations-slope/", views.rolling_correlation_slope, name="stock-correlations-slope"),
    path("stock/<str:symbol>/correlations-price", RedirectView.as_view(pattern_name="stock-correlations-price")),
    path("stock/<str:symbol>/correlations-price/", views.rolling_correlation_price, name="stock-correlations-price"),
    path("stock/<str:symbol>/historical", views.StockView.as_view(), name="stock-historical"),

    # Mutations
    path("symbol/<str:symbol>/add-days/", views.add_days, name="add-days"),
    path("symbol/<str:symbol>/add-since/", views.add_since, name="add-since"),
    path("symbol/<str:symbol>/activate/", views.activate_symbol, name="activate-symbol"),
    path("symbol/<str:symbol>/deactivate/", views.deactivate_symbol, name="deactivate-symbol"),
    path("symbol/<str:symbol>/set-symbol-colour/", views.set_symbol_colour, name="set-symbol-colour"),

    # Data download
    path("symbol/<str:symbol>/download-single-day/<str:day>/", views.download_day, name="download-single-day"),
    path("symbol/<str:symbol>/download-multiple/", views.download_multiple, name="download-multiple"),
    path("symbol/<str:symbol>/download-all/", views.download_all, name="download-all"),

]

for group_type in Group.GroupType:
    name = group_type_name(group_type)
    urlpatterns += [
        path(f'{name}/',
             views.group_home(group_type).as_view(),
             name=f"{name}-home",
             kwargs={"group_type": group_type}),

        path(f'{name}/add/',
             views.add_group,
             name=f"{name}-add",
             kwargs={"group_type": group_type}),

        path(f'{name}/<slug:slug>/',
             views.view_group,
             name=f"{name}-view",
             kwargs={"group_type": group_type}),

        path(f'{name}/<slug:slug>/edit/',
             views.GroupEditView.as_view(),
             name=f"{name}-edit",
             kwargs={"group_type": group_type}),

        path(f'{name}/<slug:slug>/update/',
             views.update_group,
             name=f"{name}-update",
             kwargs={"group_type": group_type}),

        path(f'{name}/<slug:slug>/delete/',
             views.delete_group,
             name=f"{name}-delete",
             kwargs={"group_type": group_type}),

        path(f'{name}/<slug:slug>/rename/',
             views.rename_group,
             name=f"{name}-rename",
             kwargs={"group_type": group_type}),
    ]
