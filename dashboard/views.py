from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard_view(request):
    # Placeholder context data
    context = {
        'total_users': 150, # Example data
        'total_orders': 75,
        'total_products': 300,
        'total_articles': 45,
        # Add more data as needed for charts or info boxes
    }
    return render(request, 'dashboard/index.html', context)
