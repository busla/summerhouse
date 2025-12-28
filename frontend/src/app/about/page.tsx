import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'About | Summerhouse Quesada',
  description: 'Learn about Summerhouse Quesada, a beautiful vacation rental in Ciudad Quesada, Costa Blanca, Spain. Sleeps up to 4 guests.',
};

const propertyHighlights = {
  bedrooms: 2,
  bathrooms: 1,
  maxGuests: 4,
  size: '75 m²',
  features: [
    'Private terrace with garden views',
    'Community pool access',
    'Air conditioning throughout',
    'Fully equipped kitchen',
    'Free WiFi',
    'Private parking',
    'Smart TV with streaming',
    'Washing machine',
  ],
};

const amenities = {
  kitchen: [
    'Full-size refrigerator',
    'Ceramic hob',
    'Microwave',
    'Toaster & kettle',
    'Coffee maker',
    'Dishwasher',
    'Complete cookware & utensils',
  ],
  bathroom: [
    'Walk-in shower',
    'Fresh towels provided',
    'Hairdryer',
    'Toiletries',
  ],
  bedroom: [
    'Quality linens',
    'Blackout curtains',
    'Wardrobe space',
    'Extra blankets',
  ],
  outdoor: [
    'Private terrace',
    'Garden furniture',
    'BBQ grill',
    'Community pool',
    'Sun loungers at pool',
  ],
  entertainment: [
    'Smart TV',
    'Netflix & streaming apps',
    'Board games',
    'Books & magazines',
  ],
};

export default function AboutPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">About Summerhouse Quesada</h1>

      {/* Hero Description */}
      <div className="prose prose-lg max-w-none mb-12">
        <p className="text-gray-600 text-lg leading-relaxed">
          Welcome to Summerhouse Quesada, your perfect holiday retreat in the heart of Costa Blanca.
          This beautifully maintained apartment offers the ideal base for exploring the stunning
          beaches, world-class golf courses, and vibrant local culture of southeastern Spain.
        </p>
        <p className="text-gray-600 leading-relaxed">
          Located in the popular residential area of Ciudad Quesada, our property combines
          comfort and convenience with authentic Spanish charm. Whether you&apos;re seeking a
          relaxing beach holiday, an active golf trip, or a family adventure, Summerhouse
          Quesada has everything you need.
        </p>
      </div>

      {/* Property Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
        <div className="bg-blue-50 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold text-blue-600">{propertyHighlights.bedrooms}</div>
          <div className="text-sm text-gray-600">Bedrooms</div>
        </div>
        <div className="bg-blue-50 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold text-blue-600">{propertyHighlights.bathrooms}</div>
          <div className="text-sm text-gray-600">Bathroom</div>
        </div>
        <div className="bg-blue-50 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold text-blue-600">{propertyHighlights.maxGuests}</div>
          <div className="text-sm text-gray-600">Max Guests</div>
        </div>
        <div className="bg-blue-50 p-4 rounded-lg text-center">
          <div className="text-3xl font-bold text-blue-600">{propertyHighlights.size}</div>
          <div className="text-sm text-gray-600">Living Space</div>
        </div>
      </div>

      {/* Key Features */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Key Features</h2>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {propertyHighlights.features.map((feature) => (
            <li key={feature} className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-gray-700">{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Detailed Amenities */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-6">Amenities</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Object.entries(amenities).map(([category, items]) => (
            <div key={category} className="bg-gray-50 p-4 rounded-lg">
              <h3 className="font-medium text-gray-800 mb-3 capitalize">{category}</h3>
              <ul className="space-y-2">
                {items.map((item) => (
                  <li key={item} className="text-sm text-gray-600 flex items-start gap-2">
                    <span className="text-blue-500 mt-1">•</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* House Rules */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">House Rules</h2>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <ul className="space-y-3 text-gray-700">
            <li className="flex items-start gap-3">
              <span className="font-medium min-w-[100px]">Check-in:</span>
              <span>After 3:00 PM</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="font-medium min-w-[100px]">Check-out:</span>
              <span>Before 10:00 AM</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="font-medium min-w-[100px]">No smoking:</span>
              <span>Smoking is not permitted inside the property</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="font-medium min-w-[100px]">Pets:</span>
              <span>Sorry, pets are not allowed</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="font-medium min-w-[100px]">Parties:</span>
              <span>No parties or events</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="font-medium min-w-[100px]">Quiet hours:</span>
              <span>10:00 PM - 8:00 AM (community rules)</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Your Host */}
      <div className="bg-blue-50 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Your Hosts</h2>
        <p className="text-gray-600 mb-4">
          We&apos;re a family who fell in love with the Costa Blanca many years ago.
          We take pride in maintaining our property to the highest standards and
          ensuring every guest has a memorable stay.
        </p>
        <p className="text-gray-600">
          While we may not be on-site, we&apos;re always available to help with any
          questions or concerns. Our local property manager can assist with any
          urgent matters during your stay.
        </p>
      </div>
    </div>
  );
}
