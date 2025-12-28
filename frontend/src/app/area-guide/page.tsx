import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Area Guide | Summerhouse Quesada',
  description: 'Discover Ciudad Quesada and Costa Blanca - beaches, golf, restaurants, attractions, and local tips for your Costa Blanca holiday.',
};

const beaches = [
  {
    name: 'Guardamar Beach',
    distance: '15 km',
    description: 'Long sandy beach with dunes, pine forests, and Blue Flag status. Perfect for families.',
  },
  {
    name: 'La Mata Beach',
    distance: '18 km',
    description: 'Popular beach with great facilities, restaurants, and a lively promenade.',
  },
  {
    name: 'Torrevieja Beaches',
    distance: '15 km',
    description: 'Multiple beaches including Playa del Cura, with all amenities in walking distance.',
  },
  {
    name: 'Orihuela Costa Beaches',
    distance: '10 km',
    description: 'La Zenia and Cabo Roig offer crystal-clear waters and excellent beach bars.',
  },
];

const golfCourses = [
  {
    name: 'La Marquesa Golf',
    distance: '3 km',
    description: '18-hole course designed by Justo Quesada. Challenging and scenic.',
  },
  {
    name: 'La Finca Golf',
    distance: '8 km',
    description: 'Championship course with excellent facilities and practice areas.',
  },
  {
    name: 'Villamartin Golf',
    distance: '12 km',
    description: 'Established course with beautiful gardens and clubhouse.',
  },
  {
    name: 'Campoamor Golf',
    distance: '15 km',
    description: 'Scenic course with sea views and well-maintained greens.',
  },
];

const attractions = [
  {
    name: 'Torrevieja Salt Lakes',
    type: 'Nature',
    description: 'Famous pink salt lakes with therapeutic properties. Spectacular photo opportunities.',
  },
  {
    name: 'La Zenia Boulevard',
    type: 'Shopping',
    description: 'Large open-air shopping center with 150+ stores, restaurants, and cinema.',
  },
  {
    name: 'Elche Palm Grove',
    type: 'UNESCO Site',
    description: 'Europe\'s largest palm grove, a UNESCO World Heritage Site. Beautiful gardens.',
  },
  {
    name: 'Alicante Old Town',
    type: 'Culture',
    description: 'Historic center with Santa Barbara Castle, museums, and vibrant nightlife.',
  },
  {
    name: 'Rio Safari Elche',
    type: 'Family',
    description: 'Zoo and water park with animal shows, perfect for families with children.',
  },
  {
    name: 'Aquopolis Torrevieja',
    type: 'Water Park',
    description: 'Water park with slides and pools. Great summer fun for all ages.',
  },
];

const localDining = [
  {
    name: 'Quesada Town Centre',
    type: 'Restaurants & Bars',
    description: 'A variety of Spanish and international restaurants within walking distance.',
  },
  {
    name: 'Torrevieja Paseo',
    type: 'Seafood',
    description: 'Seafront promenade lined with excellent seafood restaurants.',
  },
  {
    name: 'Rojales',
    type: 'Traditional Spanish',
    description: 'Authentic tapas bars and local eateries in this charming town.',
  },
];

const markets = [
  { name: 'Rojales Market', day: 'Thursday', description: 'Large weekly market with local produce, clothes, and crafts' },
  { name: 'Torrevieja Market', day: 'Friday', description: 'Huge market along the seafront, great for souvenirs' },
  { name: 'La Marina Market', day: 'Sunday', description: 'Popular car boot and flea market' },
];

export default function AreaGuidePage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Area Guide</h1>

      <p className="text-gray-600 mb-8 text-lg">
        Ciudad Quesada is a wonderful base for exploring the Costa Blanca. From stunning
        beaches to world-class golf, traditional markets to modern shopping, there&apos;s
        something for everyone within easy reach of Summerhouse Quesada.
      </p>

      {/* Beaches */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">🏖️</span> Beaches
        </h2>
        <p className="text-gray-600 mb-4">
          The Costa Blanca boasts some of Spain&apos;s best beaches, with warm Mediterranean
          waters and over 300 days of sunshine per year.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {beaches.map((beach) => (
            <div key={beach.name} className="border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-medium text-gray-800">{beach.name}</h3>
                <span className="text-sm text-blue-600 bg-blue-50 px-2 py-1 rounded">{beach.distance}</span>
              </div>
              <p className="text-sm text-gray-600">{beach.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Golf */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">⛳</span> Golf Courses
        </h2>
        <p className="text-gray-600 mb-4">
          The region is a golfer&apos;s paradise with over 20 courses within 30 minutes drive.
          Year-round sunshine makes it perfect for golf any time of year.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {golfCourses.map((course) => (
            <div key={course.name} className="border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-medium text-gray-800">{course.name}</h3>
                <span className="text-sm text-green-600 bg-green-50 px-2 py-1 rounded">{course.distance}</span>
              </div>
              <p className="text-sm text-gray-600">{course.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Attractions */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">🎯</span> Attractions
        </h2>
        <div className="grid grid-cols-1 gap-4">
          {attractions.map((attraction) => (
            <div key={attraction.name} className="border border-gray-200 rounded-lg p-4 flex flex-col md:flex-row md:items-start gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="font-medium text-gray-800">{attraction.name}</h3>
                  <span className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded">{attraction.type}</span>
                </div>
                <p className="text-sm text-gray-600">{attraction.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Dining */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">🍽️</span> Dining
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {localDining.map((place) => (
            <div key={place.name} className="bg-orange-50 rounded-lg p-4">
              <h3 className="font-medium text-gray-800 mb-1">{place.name}</h3>
              <p className="text-sm text-orange-700 mb-2">{place.type}</p>
              <p className="text-sm text-gray-600">{place.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Markets */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="text-2xl">🛒</span> Local Markets
        </h2>
        <p className="text-gray-600 mb-4">
          Weekly markets are a Spanish tradition. Stock up on fresh produce, find unique
          souvenirs, or simply enjoy the atmosphere.
        </p>
        <div className="bg-gray-50 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Market</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Day</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Description</th>
              </tr>
            </thead>
            <tbody>
              {markets.map((market, index) => (
                <tr key={market.name} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="py-3 px-4 font-medium text-gray-800">{market.name}</td>
                  <td className="py-3 px-4 text-blue-600">{market.day}</td>
                  <td className="py-3 px-4 text-gray-600 text-sm">{market.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Local Tips */}
      <section className="bg-blue-50 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Local Tips</h2>
        <ul className="space-y-3 text-gray-700">
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">•</span>
            <span><strong>Siesta:</strong> Many local shops close 2-5 PM. Plan accordingly!</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">•</span>
            <span><strong>Dining times:</strong> Spanish lunch is 2-4 PM, dinner from 9 PM.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">•</span>
            <span><strong>Car rental:</strong> Highly recommended for exploring the area.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">•</span>
            <span><strong>Sun protection:</strong> UV can be strong year-round. Bring sunscreen!</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">•</span>
            <span><strong>Language:</strong> English is widely spoken in tourist areas.</span>
          </li>
        </ul>
      </section>
    </div>
  );
}
