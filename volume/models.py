import dataclasses
import datetime

from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse
from timescale.db.models.models import TimescaleModel, TimescaleDateTimeField


def unique_slug(instance, name):
    base_slug = slugify(name)
    slug = base_slug
    class_ = instance.__class__
    n = 1
    while class_.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    return slug


@dataclasses.dataclass
class MinuteData:
    time: datetime.datetime
    symbol: str
    last: float
    volume: int
    cumulative_volume: int
    last_mid_before: float
    slope: int


class SymbolQuerySet(models.QuerySet):
    def stocks(self, **kwargs):
        return self.filter(type=Symbol.Type.STOCK, **kwargs)

    def indices(self, **kwargs):
        return self.filter(type=Symbol.Type.INDEX, **kwargs)


class Symbol(models.Model):
    class Type(models.TextChoices):
        STOCK = "S", "Stock"
        INDEX = "I", "Index"

    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.TextField(default="", blank=True)
    active = models.BooleanField(default=True, db_index=True)
    type = models.CharField(max_length=1,
                            choices=Type.choices,
                            default=Type.STOCK,
                            db_index=True)
    colour = models.CharField(max_length=7, null=True)
    api_symbol = models.CharField(max_length=30, null=True)

    objects = SymbolQuerySet.as_manager()

    def __str__(self):
        return str(self.display_name)

    def get_absolute_url(self):
        if self.type == self.Type.STOCK:
            return reverse("stock-historical", kwargs={"symbol": self.symbol})
        else:
            return reverse("index-historical", kwargs={"symbol": self.symbol})

    @property
    def display_name(self):
        if self.name:
            return self.name
        else:
            return self.symbol

    @property
    def is_stock(self):
        return self.type == self.Type.STOCK

    @property
    def is_index(self):
        return self.type == self.Type.INDEX

    class Meta:
        ordering = ["type", "active", "symbol"]


class SystemSetting(models.Model):
    class Type(models.TextChoices):
        BOOLEAN = "B", "boolean"
        INTEGER = "I", "integer"
        STRING = "S", "string"
        FLOAT = "F", "float"

    name = models.TextField(db_index=True)
    data_type = models.CharField(max_length=1,
                                 choices=Type.choices,
                                 default=Type.BOOLEAN)
    bool_value = models.BooleanField(null=True, blank=True)
    int_value = models.IntegerField(null=True, blank=True)
    string_value = models.TextField(null=True, blank=True)
    float_value = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}: {self.value}"

    @property
    def value(self):
        if self.data_type == self.Type.BOOLEAN:
            return self.bool_value
        elif self.data_type == self.Type.INTEGER:
            return self.int_value
        elif self.data_type == self.Type.STRING:
            return self.string_value
        elif self.data_type == self.Type.FLOAT:
            return self.float_value

    def set_value(self, value):
        if self.data_type == self.Type.BOOLEAN:
            self.bool_value = value
        elif self.data_type == self.Type.INTEGER:
            self.int_value = value
        elif self.data_type == self.Type.STRING:
            self.string_value = value
        elif self.data_type == self.Type.FLOAT:
            self.float_value = value


class IndexWeight(models.Model):
    index = models.ForeignKey(Symbol,
                              on_delete=models.CASCADE,
                              related_name="weights",
                              db_index=True)
    symbol = models.CharField(max_length=10)
    weight = models.DecimalField(max_digits=12, decimal_places=10)

    @property
    def weight_percent(self):
        return 100*self.weight

    def __str__(self):
        return f"{self.index}: {self.symbol} = {self.weight}"


class Chart(models.Model):
    class DataType(models.TextChoices):
        VOLUME = "V", "Volume"
        SLOPE = "S", "Slope"

    name = models.TextField()
    slug = models.SlugField()
    symbols = models.ManyToManyField(Symbol, related_name="+")
    added = models.DateTimeField(auto_now_add=True)
    data_type = models.CharField(max_length=1,
                                 choices=DataType.choices,
                                 default=DataType.VOLUME)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ["added"]


class Group(models.Model):
    class GroupType(models.TextChoices):
        VOLUME_CHART = "V", "Volume Chart"
        SLOPE_CHART = "S", "Slope Chart"
        CORRELATION_TABLE = "C", "Correlation Table"
        SLOPE_TABLE = "T", "Slope Table"
        COMPARISON_TABLE = "O", "Comparison Table"


    name = models.TextField()
    slug = models.SlugField(db_index=True)
    symbols = models.ManyToManyField(Symbol, related_name="+")
    added = models.DateTimeField(auto_now_add=True)
    group_type = models.CharField(max_length=1, choices=GroupType.choices, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        return super().save(*args, **kwargs)

    @property
    def group_type_name(self):
        return group_type_name(self.group_type)

    class Meta:
        ordering = ["added"]


GROUP_TYPE_LOOKUP = {
    Group.GroupType.VOLUME_CHART: "volume",
    Group.GroupType.SLOPE_CHART: "slope",
    Group.GroupType.CORRELATION_TABLE: "correlation",
    Group.GroupType.SLOPE_TABLE: "slope-table",
    Group.GroupType.COMPARISON_TABLE: "comparison",
}

def group_type_name(group_type):
    return GROUP_TYPE_LOOKUP[group_type]


class Correlation(models.Model):
    class DataType(models.TextChoices):
        VOLUME = "V", "Volume"
        SLOPE = "S", "Slope"

    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    day = models.DateField(db_index=True)
    data_type = models.CharField(max_length=1,
                                 choices=DataType.choices)

    x_mean = models.FloatField(null=True, default=0)
    y_mean = models.FloatField(null=True, default=0)
    N = models.FloatField(null=True, default=0)
    D = models.FloatField(null=True, default=0)
    E = models.FloatField(null=True, default=0)
    n = models.IntegerField(null=True, default=0)
    value = models.FloatField()

    def __str__(self):
        return f"{self.symbol}:{self.day:%F}:{self.data_type}"

    class Meta:
        ordering = ["day"]
        indexes = [
            models.Index(fields=["symbol", "day", "data_type"]),
        ]


class MarketHoliday(models.Model):
    day = models.DateField(db_index=True)
    exchange = models.TextField(blank=True)
    status = models.TextField(blank=True)
    name = models.TextField(blank=True)
    open = models.DateTimeField(null=True, blank=True)
    close = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.day}:{self.name} ({self.exchange})"

    class Meta:
        ordering = ["day"]


class RollingCorrelation(TimescaleModel):
    class DataType(models.TextChoices):
        VOLUME = "V", "Volume"
        SLOPE = "S", "Slope"

    time = TimescaleDateTimeField(interval="1 day")
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    data_type = models.CharField(max_length=1,
                                 choices=DataType.choices)
    window = models.IntegerField()
    value = models.FloatField()

    def __str__(self):
        return f"{self.symbol}:{self.time:%F %T}:{self.data_type}"

    class Meta:
        ordering = ["time"]
        indexes = [
            models.Index(fields=["time"]),
            models.Index(fields=["symbol", "time"]),
            models.Index(fields=["symbol", "data_type", "window", "time"]),
        ]


class DataDay(models.Model):
    class State(models.TextChoices):
        COMPLETE = "C", "Complete"
        PENDING = "P", "Pending"
        LIVE = "L", "Live"
        # ABSENT = "A", "Absent"

    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    day = models.DateField()
    state = models.CharField(max_length=1,
                             choices=State.choices,
                             default=State.PENDING,
                             db_index=True)
    last_tried = models.DateTimeField(null=True, db_index=True, blank=True)

    def __str__(self):
        return f"{self.symbol}:{self.day:%F}"

    @property
    def has_data(self):
        return self.state in (DataDay.State.COMPLETE, DataDay.State.LIVE)

    class Meta:
        ordering = ["day"]
        indexes = [
            models.Index(fields=["symbol", "day"]),
        ]


class IncomingPrice(models.Model):
    symbol = models.CharField(max_length=10, db_index=True)
    time = models.DateTimeField()
    last_mid_before = models.DecimalField(max_digits=12, decimal_places=4, null=True)

    def __str__(self):
        return f"{self.symbol} at {self.time:%F %T}: {self.last_mid_before}"

    class Meta:
        indexes = [
            models.Index(fields=["symbol", "time"]),
        ]


class Minute(TimescaleModel):
    time = TimescaleDateTimeField(interval="1 day")
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    last = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    volume = models.IntegerField()
    cumulative_volume = models.IntegerField(null=True)
    last_mid_before = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    slope = models.IntegerField(null=True)

    def __str__(self):
        return f"{self.symbol}:{self.time:%F %T}"

    class Meta:
        ordering = ["time"]
        indexes = [
            models.Index(fields=["time"]),
            models.Index(fields=["symbol", "time"]),
        ]

    @classmethod
    def from_minute_data(cls, md, symbol_obj=None):
        if symbol_obj is None:
            symbol_obj = Symbol.objects.get(symbol=md.symbol)

        return cls(
            time=md.time,
            symbol=symbol_obj,
            last=md.last,
            volume=md.volume,
            cumulative_volume=md.cumulative_volume,
            last_mid_before=md.last_mid_before,
            slope=md.slope,
        )
