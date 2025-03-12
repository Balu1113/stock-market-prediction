<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Market Prediction</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1, h2, h3 {
            color: #333;
            text-align: center;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #666;
        }
        input[type="file"],
        input[type="number"],
        select {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
        }
        button:hover {
            background-color: #45a049;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
        }
        .metric-card {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }
        .metric-value {
            font-size: 24px;
            color: #2196F3;
        }
        .trading-metrics {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
        }
        .trading-card {
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }
        .trading-value {
            font-size: 20px;
            color: #1565c0;
        }
        #error-message {
            color: #ff0000;
            margin: 10px 0;
            display: none;
        }
        #loading {
            text-align: center;
            display: none;
            margin: 20px 0;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #2196F3;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 Stock Market Prediction</h1>

        <form id="prediction-form" enctype="multipart/form-data">
            <div class="form-group">
                <label for="file">Upload CSV File (with Date and Close columns)</label>
                <input type="file" id="file" name="file" accept=".csv" required>
            </div>

            <div class="form-group">
                <label for="model_type">Select Model</label>
                <select id="model_type" name="model_type">
                    <option value="Linear Regression">Linear Regression</option>
                    <option value="Random Forest">Random Forest</option>
                </select>
            </div>

            <div class="form-group">
                <label>Feature Engineering</label>
                <div>
                    <input type="checkbox" name="features[]" value="Moving Average" checked> Moving Average
                    <input type="checkbox" name="features[]" value="RSI" checked> RSI
                    <input type="checkbox" name="features[]" value="MACD" checked> MACD
                </div>
            </div>

            <div class="form-group">
                <label for="train_size">Training Data Size (%)</label>
                <input type="number" id="train_size" name="train_size" value="80" min="50" max="90">
            </div>

            <div class="form-group">
                <label for="prediction_days">Prediction Days</label>
                <input type="number" id="prediction_days" name="prediction_days" value="7" min="1" max="30">
            </div>

            <div class="form-group">
                <label>Enable Trading Simulation</label>
                <label class="switch">
                    <input type="checkbox" name="simulate_trading" id="simulate_trading">
                    <span class="slider"></span>
                </label>
            </div>

            <div class="form-group" id="trading_options" style="display: none;">
                <label for="initial_capital">Initial Capital ($)</label>
                <input type="number" id="initial_capital" name="initial_capital" value="10000" min="1000">
            </div>

            <button type="submit">Analyze & Predict</button>
        </form>

        <div id="error-message"></div>
        <div id="loading">Processing... Please wait.</div>

        <div id="results" style="display: none;">
            <h2>Model Performance</h2>
            <div class="metrics">
                <div class="metric-card">
                    <h3>RMSE</h3>
                    <div id="rmse" class="metric-value">-</div>
                </div>
                <div class="metric-card">
                    <h3>MAE</h3>
                    <div id="mae" class="metric-value">-</div>
                </div>
                <div class="metric-card">
                    <h3>R² Score</h3>
                    <div id="r2" class="metric-value">-</div>
                </div>
            </div>

            <div id="trading_results" style="display: none;">
                <h2>Trading Performance</h2>
                <div class="trading-metrics">
                    <div class="trading-card">
                        <h3>Total Trades</h3>
                        <div id="total_trades" class="trading-value">-</div>
                    </div>
                    <div class="trading-card">
                        <h3>Win Rate</h3>
                        <div id="win_rate" class="trading-value">-</div>
                    </div>
                    <div class="trading-card">
                        <h3>Total P&L</h3>
                        <div id="total_pnl" class="trading-value">-</div>
                    </div>
                    <div class="trading-card">
                        <h3>Avg Return</h3>
                        <div id="avg_return" class="trading-value">-</div>
                    </div>
                    <div class="trading-card">
                        <h3>Final Capital</h3>
                        <div id="final_capital" class="trading-value">-</div>
                    </div>
                </div>
            </div>

            <div id="plot"></div>

            <h3>Future Predictions</h3>
            <div id="predictions-table"></div>
        </div>
    </div>

    <script>
        $(document).ready(function() {
            $('#simulate_trading').change(function() {
                $('#trading_options').toggle(this.checked);
            });

            $('#prediction-form').on('submit', function(e) {
                e.preventDefault();

                $('#error-message').hide();
                $('#loading').show();
                $('#results').hide();

                var formData = new FormData(this);
                formData.append('simulate_trading', $('#simulate_trading').is(':checked'));

                $.ajax({
                    url: '/predict',
                    type: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function(response) {
                        $('#loading').hide();
                        $('#results').show();

                        // Update metrics
                        $('#rmse').text('$' + response.metrics.rmse.toFixed(2));
                        $('#mae').text('$' + response.metrics.mae.toFixed(2));
                        $('#r2').text(response.metrics.r2.toFixed(3));

                        // Update trading metrics if available
                        if (response.trading_metrics && Object.keys(response.trading_metrics).length > 0) {
                            $('#trading_results').show();
                            $('#total_trades').text(response.trading_metrics.total_trades);
                            $('#win_rate').text(response.trading_metrics.win_rate.toFixed(2) + '%');
                            $('#total_pnl').text('$' + response.trading_metrics.total_pnl.toFixed(2));
                            $('#avg_return').text(response.trading_metrics.avg_return.toFixed(2) + '%');
                            $('#final_capital').text('$' + response.trading_metrics.final_capital.toFixed(2));
                        } else {
                            $('#trading_results').hide();
                        }

                        // Plot chart
                        Plotly.newPlot('plot', JSON.parse(response.plot).data, JSON.parse(response.plot).layout);

                        // Display predictions table
                        let tableHTML = '<table style="width:100%; margin-top:20px;"><tr><th>Date</th><th>Predicted Price</th></tr>';
                        for (let i = 0; i < response.future_predictions.dates.length; i++) {
                            tableHTML += `<tr><td>${response.future_predictions.dates[i]}</td><td>$${response.future_predictions.values[i].toFixed(2)}</td></tr>`;
                        }
                        tableHTML += '</table>';
                        $('#predictions-table').html(tableHTML);
                    },
                    error: function(xhr) {
                        $('#loading').hide();
                        $('#error-message').text(xhr.responseJSON?.error || 'An error occurred').show();
                    }
                });
            });
        });
    </script>
</body>
</html>