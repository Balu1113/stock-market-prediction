import os
from flask import Flask, render_template, request, jsonify
import pandas as pd
from utils.data_processor import DataProcessor
from utils.ml_models import StockPredictor
from utils.trading_strategy import TradingStrategy
import json
import plotly
import plotly.graph_objects as go
from datetime import datetime, timedelta

app = Flask(__name__)

# Ensure upload directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Process data
        data_processor = DataProcessor()
        df = data_processor.load_data(file)

        # Get parameters from form
        model_type = request.form.get('model_type', 'Linear Regression')
        train_size = float(request.form.get('train_size', 80)) / 100
        prediction_days = int(request.form.get('prediction_days', 7))
        features = request.form.getlist('features[]')
        simulate_trading = request.form.get('simulate_trading', 'false') == 'true'
        initial_capital = float(request.form.get('initial_capital', 10000))

        # Process features
        processed_data = data_processor.process_data(df, features)

        # Train model and get predictions
        predictor = StockPredictor(model_type=model_type)
        X_train, X_test, y_train, y_test, predictions, future_predictions = \
            predictor.train_and_predict(processed_data, train_size, prediction_days)

        # Calculate metrics
        metrics = predictor.calculate_metrics(y_test, predictions)

        # Create plot
        fig = go.Figure()

        # Historical data
        fig.add_trace(go.Scatter(
            x=df.index.strftime('%Y-%m-%d').tolist(),
            y=df['Close'].tolist(),
            name='Historical',
            line=dict(color='#17B897')
        ))

        # Predictions
        pred_dates = df.index[-len(predictions):].strftime('%Y-%m-%d').tolist()
        fig.add_trace(go.Scatter(
            x=pred_dates,
            y=predictions.tolist(),
            name='Predicted',
            line=dict(color='#FF6B6B', dash='dash')
        ))

        # Future predictions
        future_dates = [(df.index[-1] + timedelta(days=i+1)).strftime('%Y-%m-%d') 
                       for i in range(len(future_predictions))]
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=future_predictions.tolist(),
            name='Future Predictions',
            line=dict(color='#4A90E2', dash='dot')
        ))

        # Trading simulation
        trading_metrics = {}
        if simulate_trading:
            strategy = TradingStrategy(initial_capital=initial_capital)
            df_with_signals, trading_metrics = strategy.simulate_trades(df)

            # Add buy/sell signals to plot
            buy_signals = df_with_signals[df_with_signals['Signal'] == 1]
            sell_signals = df_with_signals[df_with_signals['Signal'] == -1]

            fig.add_trace(go.Scatter(
                x=buy_signals.index.strftime('%Y-%m-%d').tolist(),
                y=buy_signals['Close'].tolist(),
                mode='markers',
                name='Buy Signal',
                marker=dict(symbol='triangle-up', size=10, color='green')
            ))

            fig.add_trace(go.Scatter(
                x=sell_signals.index.strftime('%Y-%m-%d').tolist(),
                y=sell_signals['Close'].tolist(),
                mode='markers',
                name='Sell Signal',
                marker=dict(symbol='triangle-down', size=10, color='red')
            ))

        # Update layout
        fig.update_layout(
            title='Stock Price Prediction with Trading Signals',
            xaxis_title='Date',
            yaxis_title='Price ($)',
            template='plotly_white'
        )

        # Convert plot to JSON
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        return jsonify({
            'plot': graphJSON,
            'metrics': metrics,
            'future_predictions': {
                'dates': future_dates,
                'values': future_predictions.tolist()
            },
            'trading_metrics': trading_metrics
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
