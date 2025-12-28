import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Pricing | Summerhouse Quesada',
  description: 'View our seasonal rates and pricing for Summerhouse Quesada vacation rental in Costa Blanca, Spain.',
};

const pricingData = {
  seasons: [
    {
      name: 'Peak Season',
      period: 'July - August',
      nightlyRate: 150,
      minNights: 7,
      color: 'bg-red-100 border-red-300',
    },
    {
      name: 'High Season',
      period: 'June, September',
      nightlyRate: 130,
      minNights: 5,
      color: 'bg-orange-100 border-orange-300',
    },
    {
      name: 'Mid Season',
      period: 'April - May, October',
      nightlyRate: 100,
      minNights: 4,
      color: 'bg-yellow-100 border-yellow-300',
    },
    {
      name: 'Low Season',
      period: 'November - March',
      nightlyRate: 80,
      minNights: 3,
      color: 'bg-green-100 border-green-300',
    },
  ],
  extras: {
    cleaningFee: 50,
    securityDeposit: 200,
    earlyCheckIn: 30,
    lateCheckOut: 30,
  },
};

export default function PricingPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Pricing</h1>

      <p className="text-gray-600 mb-8">
        Our rates vary by season to give you the best value. All prices are per night
        and include all utilities, WiFi, and access to the community pool.
      </p>

      {/* Seasonal Rates Table */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Seasonal Rates</h2>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left py-3 px-4 border border-gray-200 font-semibold">Season</th>
                <th className="text-left py-3 px-4 border border-gray-200 font-semibold">Period</th>
                <th className="text-right py-3 px-4 border border-gray-200 font-semibold">Rate/Night</th>
                <th className="text-right py-3 px-4 border border-gray-200 font-semibold">Min. Nights</th>
              </tr>
            </thead>
            <tbody>
              {pricingData.seasons.map((season) => (
                <tr key={season.name} className={season.color}>
                  <td className="py-3 px-4 border border-gray-200 font-medium">{season.name}</td>
                  <td className="py-3 px-4 border border-gray-200">{season.period}</td>
                  <td className="py-3 px-4 border border-gray-200 text-right font-semibold">{season.nightlyRate}</td>
                  <td className="py-3 px-4 border border-gray-200 text-right">{season.minNights} nights</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Additional Fees */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Additional Fees</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg">
            <h3 className="font-medium text-gray-700">Cleaning Fee</h3>
            <p className="text-2xl font-bold text-gray-900">{pricingData.extras.cleaningFee}</p>
            <p className="text-sm text-gray-500">One-time fee per booking</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <h3 className="font-medium text-gray-700">Security Deposit</h3>
            <p className="text-2xl font-bold text-gray-900">{pricingData.extras.securityDeposit}</p>
            <p className="text-sm text-gray-500">Refundable after checkout</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <h3 className="font-medium text-gray-700">Early Check-in</h3>
            <p className="text-2xl font-bold text-gray-900">{pricingData.extras.earlyCheckIn}</p>
            <p className="text-sm text-gray-500">Subject to availability</p>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg">
            <h3 className="font-medium text-gray-700">Late Check-out</h3>
            <p className="text-2xl font-bold text-gray-900">{pricingData.extras.lateCheckOut}</p>
            <p className="text-sm text-gray-500">Subject to availability</p>
          </div>
        </div>
      </div>

      {/* What's Included */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">What is Included</h2>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {[
            'All utilities (electricity, water, gas)',
            'High-speed WiFi',
            'Air conditioning & heating',
            'Community pool access',
            'Private parking space',
            'Bed linens & towels',
            'Fully equipped kitchen',
            'TV with satellite channels',
          ].map((item) => (
            <li key={item} className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Cancellation Policy */}
      <div className="p-6 bg-blue-50 rounded-lg">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Cancellation Policy</h2>
        <ul className="space-y-2 text-gray-600">
          <li><strong>30+ days before check-in:</strong> Full refund</li>
          <li><strong>14-29 days before check-in:</strong> 50% refund</li>
          <li><strong>Less than 14 days:</strong> No refund</li>
        </ul>
      </div>
    </div>
  );
}
