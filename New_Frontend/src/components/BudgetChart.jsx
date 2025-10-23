import React from 'react';
import { Doughnut, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export const BudgetDonutChart = ({ budget }) => {
  const percentage = (budget.spent / budget.limit) * 100;
  const remaining = Math.max(0, budget.limit - budget.spent);

  const getColor = (percentage) => {
    if (percentage < 60) return '#10B981'; // Green
    if (percentage < 80) return '#F59E0B'; // Yellow
    return '#EF4444'; // Red
  };

  const color = getColor(percentage);
  
  const data = {
    datasets: [
      {
        data: [budget.spent, remaining],
        backgroundColor: [color, '#E5E7EB'],
        borderWidth: 0,
      },
    ],
  };

  const options = {
    cutout: '70%',
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const label = context.dataIndex === 0 ? 'Spent' : 'Remaining';
            const value = context.parsed;
            return `${label}: $${value.toFixed(2)}`;
          }
        }
      }
    },
    maintainAspectRatio: false,
  };

  return (
    <div className="relative h-32 w-32">
      <Doughnut data={data} options={options} />
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900">
            {percentage.toFixed(0)}%
          </div>
          <div className="text-xs text-gray-500">spent</div>
        </div>
      </div>
    </div>
  );
};

export const BudgetBarChart = ({ budgets }) => {
  const data = {
    labels: budgets.map(b => b.name),
    datasets: [
      {
        label: 'Spent',
        data: budgets.map(b => b.spent),
        backgroundColor: budgets.map(budget => {
          const percentage = (budget.spent / budget.limit) * 100;
          if (percentage < 60) return '#10B981';
          if (percentage < 80) return '#F59E0B';
          return '#EF4444';
        }),
        borderRadius: 4,
      },
      {
        label: 'Limit',
        data: budgets.map(b => b.limit),
        backgroundColor: '#E5E7EB',
        borderRadius: 4,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            return `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
      },
      y: {
        beginAtZero: true,
        ticks: {
          callback: function(value) {
            return '$' + value;
          }
        }
      },
    },
  };

  return (
    <div className="h-64">
      <Bar data={data} options={options} />
    </div>
  );
};