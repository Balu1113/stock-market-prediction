from django.db import models


class SavedScan(models.Model):
    name = models.CharField(max_length=120)
    rules = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Alert(models.Model):
    CONDITION_TYPES = (
        ('price_above', 'Price above'),
        ('price_below', 'Price below'),
        ('rsi_above', 'RSI above'),
        ('rsi_below', 'RSI below'),
        ('ma_cross_up', 'MA20 crosses above MA50'),
        ('ma_cross_down', 'MA20 crosses below MA50'),
        ('volume_spike', 'Volume spike'),
    )
    symbol = models.CharField(max_length=20)
    condition_type = models.CharField(max_length=20, choices=CONDITION_TYPES)
    threshold = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.symbol} {self.condition_type}'


class AlertEvent(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='events')
    triggered_at = models.DateTimeField(auto_now_add=True)
    price = models.FloatField(null=True, blank=True)
    message = models.CharField(max_length=255)

    class Meta:
        ordering = ['-triggered_at']


class Holding(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    quantity = models.FloatField()
    average_price = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['symbol']

    def __str__(self):
        return f'{self.symbol} x {self.quantity}'
