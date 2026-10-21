from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
from utils.data_processor import DataProcessor
from .analysis import analyze_dataframe

class PredictView(APIView):
    def post(self, request):
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
            model_type = request.data.get('model_type', 'Linear Regression')
            features = request.data.getlist('features[]')
            train_size = float(request.data.get('train_size', 80)) / 100
            prediction_days = int(request.data.get('prediction_days', 7))
            simulate_trading = request.data.get('simulate_trading') == 'true'
            initial_capital = float(request.data.get('initial_capital', 10000))

            processor = DataProcessor()
            df = processor.load_data(file)
            df = processor.process_data(df, features)

            results = analyze_dataframe(
                df,
                model_type=model_type,
                train_size=train_size,
                prediction_days=prediction_days,
                simulate_trading=simulate_trading,
                initial_capital=initial_capital,
            )
            return Response(results)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)