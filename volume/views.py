import datetime
import operator

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Min, Exists, OuterRef
from django.http import HttpResponse, FileResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.utils import timezone
from .models import Symbol, DataDay, IndexWeight, Chart, Correlation, Group, group_type_name, RollingCorrelation

from . import logic
from . import market
from . import api


DATE_FORMAT = "%Y-%m-%d"
CHART_DATETIME_FORMAT = "%F %T"
DAYS_ON_CHART = 3


@login_required
def auth(request):
    return HttpResponse("OK")


class StocksView(LoginRequiredMixin, ListView):
    context_object_name = "stocks"
    template_name = "stocks.html"

    def get_queryset(self):
        count_pending = Count("dataday", filter=Q(dataday__state=DataDay.State.PENDING))
        qs = Symbol.objects.stocks().order_by("symbol")
        qs = qs.annotate(pending=count_pending)
        qs = qs.annotate(first=Min("dataday__day"))
        return qs


class IndicesView(LoginRequiredMixin, ListView):
    context_object_name = "indices"
    template_name = "indices.html"

    def get_queryset(self):
        count_pending = Count("dataday", filter=Q(dataday__state=DataDay.State.PENDING))
        qs = Symbol.objects.indices().order_by("symbol")
        qs = qs.annotate(pending=count_pending)
        qs = qs.annotate(first=Min("dataday__day"))
        return qs


class ChartsView(LoginRequiredMixin, ListView):
    context_object_name = "charts"
    template_name = "charts.html"

    def get_queryset(self):
        qs = Chart.objects.order_by("added")
        qs = qs.annotate(symbols_count=Count("symbols"))
        return qs


class IndexView(LoginRequiredMixin, ListView):
    template_name = "index_historical.html"
    context_object_name = "days"

    def get_queryset(self):
        self.index = get_object_or_404(Symbol, symbol=self.kwargs["symbol"])
        return DataDay.objects.filter(symbol=self.index)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["index"] = self.index
        return context


class WeightsView(LoginRequiredMixin, ListView):
    template_name = "index_weights.html"
    context_object_name = "weights"

    def get_queryset(self):
        self.index = get_object_or_404(Symbol, symbol=self.kwargs["symbol"])
        all_symbols = set(Symbol.objects.all().values_list("symbol", flat=True))
        weights = IndexWeight.objects.filter(index=self.index).order_by("-weight")
        for weight in weights:
            weight.known_symbol = weight.symbol in all_symbols

        return weights

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["index"] = self.index
        return context


class StockView(LoginRequiredMixin, ListView):
    template_name = "stock.html"
    context_object_name = "days"

    def get_queryset(self):
        self.symbol = get_object_or_404(Symbol, symbol=self.kwargs["symbol"])
        return DataDay.objects.filter(symbol=self.symbol)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["symbol"] = self.symbol
        return context


class ChartEditView(LoginRequiredMixin, ListView):
    template_name = "chart_edit.html"
    context_object_name = "symbols"

    def get_queryset(self):
        self.chart = get_object_or_404(Chart, slug=self.kwargs["slug"])
        chart_has_symbol = self.chart.symbols.filter(symbol=OuterRef("symbol"))
        return Symbol.objects.annotate(selected=Exists(chart_has_symbol))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["chart"] = self.chart
        return context


def latest_day(request):
    day = request.GET.get("latest_day", "today")
    if day == "today":
        return datetime.date.today()
    else:
        return datetime.datetime.strptime(day, DATE_FORMAT).date()


def chart_dates(request):
    day = latest_day(request)

    is_today = day == datetime.date.today()
    previous_day = market.previous_trading_day(day)
    next_day = market.next_trading_day(day)

    current = day
    days = []
    while len(days) < DAYS_ON_CHART:
        if market.is_weekday(current):
            days.append(current)
        current = market.previous_trading_day(current)

    days.sort()
    start = min(days)
    end = max(days) + datetime.timedelta(days=1)

    return start, end, day, previous_day, next_day, is_today, days


@login_required
def correlation_view(request, slug):
    start, end, day, previous_day, next_day, is_today, days = chart_dates(request)
    holiday = logic.holiday_for_day()

    if slug is None or slug == "all":
        symbols = Symbol.objects.all()
        table_name = "All"
    else:
        group = get_object_or_404(Group, slug=slug)
        table_name = group.name
        symbols = group.symbols.all()

    volume = logic.correlation_days(day, previous_day, Correlation.DataType.VOLUME, symbols)
    slope = logic.correlation_days(day, previous_day, Correlation.DataType.SLOPE, symbols)

    return render(request, "correlations.html", locals())


def correlation_partial_table(corr_objs, data_type, day=None):
    is_today = False

    if day is None:
        day = timezone.localdate()
        is_today = True

    corr_objs.sort(key=operator.attrgetter("value"))

    previous_day = market.previous_trading_day(day)
    previous = Correlation.objects.filter(day=previous_day, data_type=data_type).select_related("symbol")

    if data_type == Correlation.DataType.VOLUME:
        table_id = "volume-table"
        url = "stock-volume"
    elif data_type == Correlation.DataType.SLOPE:
        table_id = "slope-table"
        url = "stock-slope"

    correlations = logic.correlation_dict(corr_objs, previous)

    return render_to_string("correlation_table.html", locals())


@login_required
def slope_table_view(request, slug):
    start, end, day, previous_day, next_day, is_today, days = chart_dates(request)
    holiday = logic.holiday_for_day()

    if slug is None or slug == "all":
        symbols = Symbol.objects.all()
        table_name = "All"
    else:
        group = get_object_or_404(Group, slug=slug)
        table_name = group.name
        symbols = group.symbols.all()

    if is_today:
        current_minute = market.current_minute()
    else:
        _, current_minute = market.first_last_minute(day)

    current_minute, previous_minute, previous_close, data = logic.slope_table_data(symbols, current_minute)

    return render(request, "slope_table.html", locals())


def slope_partial_table(group=None, current_minute=None):
    if current_minute is None:
        current_minute = market.current_minute()
    is_today = current_minute.date() == timezone.localdate()

    if group is None:
        symbols = Symbol.objects.all()
    else:
        symbols = group.symbols.all()

    current_minute, previous_minute, previous_close, data = logic.slope_table_data(symbols, current_minute)

    return render_to_string("slope_table_table.html", locals())


def group_slug_info(slug):
    if slug is None or slug == "all":
        symbols = Symbol.objects.all()
        table_name = "All"
    else:
        group = get_object_or_404(Group, slug=slug)
        table_name = group.name
        symbols = group.symbols.all()

    return symbols, table_name


@login_required
def comparison_table_view(request, slug):
    symbols, table_name = group_slug_info(slug)

    start_time_str = request.GET.get("start_time")
    end_time_str = request.GET.get("end_time")
    use_previous_close = bool(request.GET.get("use_previous_close", False))

    day = latest_day(request)
    start, end, day, previous_day, next_day, is_today, days = chart_dates(request)
    holiday = logic.holiday_for_day()

    if start_time_str:
        start_time = timezone.make_aware(datetime.datetime.combine(day, datetime.datetime.strptime(start_time_str, "%H:%M").time()))
    else:
        start_time, _ = market.first_last_minute(day)

    if end_time_str:
        end_time = timezone.make_aware(datetime.datetime.combine(day, datetime.datetime.strptime(end_time_str, "%H:%M").time()))
    else:
        _, end_time = market.first_last_minute(day)

    data = logic.comparison_table_data(symbols, start_time, end_time, use_previous_close)

    return render(request, "comparison_table.html", locals())


@login_required
def stock_view(request, symbol, is_slope=False, with_correlations=False):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    start, end, day, previous_day, next_day, is_today, days = chart_dates(request)
    holiday = logic.holiday_for_day()

    data = []
    tz = timezone.get_current_timezone()
    data_field_name = "slope" if is_slope else "cumulative_volume"
    data_display_name = "Slope" if is_slope else "Volume"
    right_axis_display_name = "Price"
    plot_type = "Slope" if is_slope else "Volume"

    dates = []
    volumes = []
    prices = []
    for date in days:
        qs = logic.data_day(symbol, date)
        new_dates = list(qs.values_list("time", flat=True))

        dates += new_dates
        volumes += list(qs.values_list(data_field_name, flat=True))
        prices += list(qs.values_list("last", flat=True))

        # Add break after
        if not date == timezone.localdate() and new_dates:
            dates.append(new_dates[-1] + datetime.timedelta(minutes=1))
            volumes.append(None)
            prices.append(None)

    dates = [dt.astimezone(tz).strftime(CHART_DATETIME_FORMAT) for dt in dates]
    data = [
        {
            "type": "scatter",
            "mode": "lines",
            "name": data_display_name,
            "x": dates,
            "y": volumes,
            "connectgaps": False,
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "Price",
            "x": dates,
            "y": prices,
            "yaxis": "y2",
            "connectgaps": False,
        },
    ]

    if is_slope:
        data[0]["line"] = {"color": "#2ca02c"}

    trace_indices = {
        data_display_name: 0,
        "Price": 1,
    }

    return render(request, "stock_view.html", locals())


def _rolling_correlation_view(request, symbol, against):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    start, end, day, previous_day, next_day, is_today, days = chart_dates(request)
    holiday = logic.holiday_for_day()

    data = []
    tz = timezone.get_current_timezone()
    if against == "price":
        data_field_name = "last"
        data_display_name = "Price"
    elif against == "volume":
        data_field_name = "cumulative_volume"
        data_display_name = "Volume"
    elif against == "slope":
        data_field_name = "slope"
        data_display_name = "Slope"

    right_axis_display_name = "Correlation"
    plot_type = "Correlation"

    dates = []
    volume_correlations = []
    slope_correlations = []
    against_data = []

    for date in days:
        qs = logic.data_day(symbol, date)
        new_dates = list(qs.values_list("time", flat=True))

        dates += new_dates
        against_data += list(qs.values_list(data_field_name, flat=True))

        volume_qs = logic.rolling_correlation_data_day(symbol, date, RollingCorrelation.DataType.VOLUME)
        slope_qs = logic.rolling_correlation_data_day(symbol, date, RollingCorrelation.DataType.SLOPE)

        volume_dict = {m.time: m.value for m in volume_qs}
        volume_correlations += [volume_dict.get(date) for date in new_dates]

        slope_dict = {m.time: m.value for m in slope_qs}
        slope_correlations += [slope_dict.get(date) for date in new_dates]

        # Add break after
        if not date == timezone.localdate():
            if new_dates:
                dates.append(new_dates[-1] + datetime.timedelta(minutes=1))
                against_data.append(None)
                volume_correlations.append(None)
                slope_correlations.append(None)

    dates = [dt.astimezone(tz).strftime(CHART_DATETIME_FORMAT) for dt in dates]

    data = [
        {
            "type": "scatter",
            "mode": "lines",
            "name": data_display_name,
            "x": dates,
            "y": against_data,
            "connectgaps": False,
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "Volume Correlation (15m)",
            "x": dates,
            "y": volume_correlations,
            "yaxis": "y2",
            "connectgaps": False,
            "line": {
                "color": "#d62728",
            },
            "hovertemplate": "%{y:,.2f}",
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "Slope Correlation (15m)",
            "x": dates,
            "y": slope_correlations,
            "yaxis": "y2",
            "connectgaps": False,
            "line": {
                "color": "#9467bd",
            },
            "hovertemplate": "%{y:,.2f}",
        },
    ]

    if against == "price":
        data[0]["line"] = {"color": "#ff7f0e"}
    elif against == "slope":
        data[0]["line"] = {"color": "#2ca02c"}

    trace_indices = {
        data_display_name: 0,
        "Volume Correlation (15m)": 1,
        "Slope Correlation (15m)": 2,
    }

    return render(request, "stock_view.html", locals())


@login_required
def rolling_correlation_volume(request, symbol):
    return _rolling_correlation_view(request, symbol, "volume")


@login_required
def rolling_correlation_slope(request, symbol):
    return _rolling_correlation_view(request, symbol, "slope")


@login_required
def rolling_correlation_price(request, symbol):
    return _rolling_correlation_view(request, symbol, "price")


@login_required
def stock_view_slope(request, symbol):
    return stock_view(request, symbol, is_slope=True)


@login_required
def chart_view(request, slug=None, is_slope=False):
    start, end, day, previous_day, next_day, is_today, days = chart_dates(request)
    holiday = logic.holiday_for_day()

    if slug is None or slug == "all":
        symbols = Symbol.objects.all()
        chart_name = "Slope" if is_slope else "Volume"
    else:
        group = get_object_or_404(Group, slug=slug)
        chart_name = group.name
        symbols = group.symbols.all()

        is_slope = group.group_type == Group.GroupType.SLOPE_CHART

    plot_type = "Slope" if is_slope else "Volume"
    data_field_name = "slope" if is_slope else "cumulative_volume"

    data = []
    tz = timezone.get_current_timezone()

    for symbol in symbols:
        dates = []
        volumes = []
        for date in days:
            qs = logic.data_day(symbol.symbol, date)
            new_dates = list(qs.values_list("time", flat=True))

            dates += new_dates
            volumes += list(qs.values_list(data_field_name, flat=True))

            # Add break after
            if not date == timezone.localdate() and new_dates:
                dates.append(new_dates[-1] + datetime.timedelta(minutes=1))
                volumes.append(None)

        dates = [dt.astimezone(tz).strftime(CHART_DATETIME_FORMAT) for dt in dates]
        series = {
            "type": "scatter",
            "mode": "lines",
            "name": symbol.display_name,
            "x": dates,
            "y": volumes,
            "connectgaps": False,
        }

        if symbol.colour is not None:
            series["line"] = {
                "color": symbol.colour,
            }

        data.append(series)

    trace_indices = {symbol.symbol: i for i, symbol in enumerate(symbols)}

    return render(request, "chart.html", locals())


def group_home(group_type):
    class GroupsView(LoginRequiredMixin, ListView):
        context_object_name = "groups"
        template_name = "groups.html"

        def get_queryset(self):
            qs = Group.objects.filter(group_type=group_type).order_by("added")
            qs = qs.annotate(symbols_count=Count("symbols"))
            return qs

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["group_type"] = group_type
            context["group_type_name"] = group_type_name(group_type)
            return context

    return GroupsView


def view_group(request, slug, group_type):
    if group_type == Group.GroupType.VOLUME_CHART:
        return chart_view(request, slug, is_slope=False)
    elif group_type == Group.GroupType.SLOPE_CHART:
        return chart_view(request, slug, is_slope=True)
    elif group_type == Group.GroupType.CORRELATION_TABLE:
        return correlation_view(request, slug)
    elif group_type == Group.GroupType.SLOPE_TABLE:
        return slope_table_view(request, slug)
    elif group_type == Group.GroupType.COMPARISON_TABLE:
        return comparison_table_view(request, slug)


class GroupEditView(LoginRequiredMixin, ListView):
    template_name = "group_edit.html"
    context_object_name = "symbols"

    def get_queryset(self):
        self.group = get_object_or_404(Group, slug=self.kwargs["slug"])
        group_has_symbol = self.group.symbols.filter(symbol=OuterRef("symbol"))
        return Symbol.objects.annotate(selected=Exists(group_has_symbol))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.group
        context["group_type_name"] = group_type_name(self.group.group_type)
        return context


@require_POST
@login_required
def add_chart(request):
    name = request.POST["name"]
    if name:
        logic.add_chart(name)
    return redirect("charts")


@require_POST
@login_required
def add_group(request, group_type):
    name = request.POST["name"]
    if name:
        logic.add_group(name, group_type)
    return redirect(group_type_name(group_type) + "-home")


@require_POST
@login_required
def update_chart(request, slug):
    selected = request.POST.getlist("symbols")
    logic.update_chart(slug, selected)
    return redirect("chart-edit", slug)


@require_POST
@login_required
def update_group(request, slug, group_type):
    selected = request.POST.getlist("symbols")
    logic.update_group(slug, selected)
    return redirect(group_type_name(group_type) + "-edit", slug)


@require_POST
@login_required
def delete_chart(request, slug):
    logic.delete_chart(slug)
    return redirect("charts")


@require_POST
@login_required
def delete_group(request, slug, group_type):
    logic.delete_group(slug)
    return redirect(group_type_name(group_type) + "-home")


@require_POST
@login_required
def rename_chart(request, slug):
    name = request.POST["name"]
    logic.rename_chart(slug, name)
    return redirect("chart-edit", slug)


@require_POST
@login_required
def rename_group(request, slug, group_type):
    name = request.POST["name"]
    logic.rename_group(slug, name)
    return redirect(group_type_name(group_type) + "-edit", slug)


@require_POST
@login_required
def change_chart_type(request, slug):
    data_type = request.POST["data_type"]
    logic.change_chart_type(slug, data_type)
    return redirect("chart-edit", slug)


def redirect_to_symbol(symbol):
    sym = get_object_or_404(Symbol, symbol=symbol)
    return redirect(sym)


@require_POST
@login_required
def add_stock(request):
    symbol = request.POST["symbol"]
    logic.add_symbol(symbol)
    return redirect("stocks")


@require_POST
@login_required
def add_days(request, symbol):
    days = int(request.POST["days"])
    logic.queue_past_days(symbol, days)
    return redirect_to_symbol(symbol)


@require_POST
@login_required
def add_since(request, symbol):
    start_date = datetime.datetime.strptime(request.POST["start_date"], DATE_FORMAT).date()
    logic.queue_days_since(symbol, start_date)
    return redirect_to_symbol(symbol)


@require_POST
@login_required
def activate_symbol(request, symbol):
    logic.activate_symbol(symbol)
    return redirect_to_symbol(symbol)


@require_POST
@login_required
def deactivate_symbol(request, symbol):
    logic.deactivate_symbol(symbol)
    return redirect_to_symbol(symbol)


@require_POST
@login_required
def set_symbol_colour(request, symbol):
    colour = request.POST["colour"]
    if colour == "default":
        colour = None
    logic.set_symbol_colour(symbol, colour)
    return redirect_to_symbol(symbol)


def streaming_csv_response(csv_generator, filename):
    return StreamingHttpResponse(csv_generator, headers={
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename={}".format(filename),
    })


def csv_response(csv, filename):
    return HttpResponse(csv, headers={
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename={}".format(filename),
    })

@login_required
def download_all(request, symbol):
    name = logic.name_for_symbol(symbol)
    csv = logic.stream_data_csv(logic.data_all(symbol))
    return streaming_csv_response(csv, f"{name}.csv")


@require_POST
@login_required
def download_multiple(request, symbol):
    name = logic.name_for_symbol(symbol)
    days = [datetime.datetime.strptime(d, DATE_FORMAT) for d in request.POST.getlist("day")]
    csv = logic.stream_data_csv(logic.data_multiple(symbol, days))
    return streaming_csv_response(csv, f"{name}.csv")

@login_required
def download_day(request, symbol, day):
    name = logic.name_for_symbol(symbol)
    day = datetime.datetime.strptime(day, DATE_FORMAT).date()
    csv = logic.stream_data_csv(logic.data_day(symbol, day))
    filename = f"{name} {day:{DATE_FORMAT}}.csv"
    return streaming_csv_response(csv, filename)


@require_POST
@login_required
def live_updates_start(request):
    logic.live_updates_start()
    return redirect("system")


@require_POST
@login_required
def live_updates_pause(request):
    logic.live_updates_pause()
    return redirect("system")


@login_required
def api_test(request):
    params = {
        "timestamp.lt": 1692040789000000000,
        "sort": "timestamp",
        "order": "desc",
        "limit": 1,
    }
    r_json = api.base_api_request("/vX/quotes/AAPL", params, raise_for_status=False)
    status = r_json.get("status")
    message = r_json.get("message")
    success = status == "OK"

    return render(request, "api_test_partial.html", locals())
