import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Location | Summerhouse Quesada',
  description: 'Find Summerhouse Quesada vacation rental in Ciudad Quesada, Alicante, Costa Blanca, Spain. View map and directions.',
};

const locationData = {
  address: {
    street: 'Calle del Sol 45',
    city: 'Ciudad Quesada',
    region: 'Alicante',
    country: 'Spain',
    postalCode: '03170',
  },
  coordinates: {
    lat: 38.0731,
    lng: -0.7835,
  },
  distances: [
    { place: 'Alicante-Elche Airport (ALC)', distance: '45 km', time: '40 min' },
    { place: 'Murcia-San Javier Airport (RMU)', distance: '35 km', time: '30 min' },
    { place: 'Torrevieja town center', distance: '15 km', time: '15 min' },
    { place: 'La Marquesa Golf', distance: '3 km', time: '5 min' },
    { place: 'Guardamar Beach', distance: '15 km', time: '15 min' },
    { place: 'La Zenia Boulevard (shopping)', distance: '10 km', time: '12 min' },
  ],
};

export default function LocationPage() {
  const googleMapsUrl = `https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d12702.04!2d${locationData.coordinates.lng}!3d${locationData.coordinates.lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0xd63a9f8c8c8c8c8%3A0x0!2sCiudad%20Quesada!5e0!3m2!1sen!2ses!4v1`;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Location</h1>

      <p className="text-gray-600 mb-8">
        Summerhouse Quesada is located in the heart of Ciudad Quesada, a popular
        residential area on Spain&apos;s beautiful Costa Blanca. The property is
        perfectly positioned for both golf enthusiasts and beach lovers.
      </p>

      {/* Address Card */}
      <div className="mb-8 p-6 bg-gray-50 rounded-lg">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Address</h2>
        <address className="not-italic text-gray-600">
          <p className="font-medium text-gray-800">{locationData.address.street}</p>
          <p>{locationData.address.city}</p>
          <p>{locationData.address.postalCode} {locationData.address.region}</p>
          <p>{locationData.address.country}</p>
        </address>
        <div className="mt-4">
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${locationData.coordinates.lat},${locationData.coordinates.lng}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-800"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Open in Google Maps
          </a>
        </div>
      </div>

      {/* Map */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Map</h2>
        <div className="aspect-video bg-gray-200 rounded-lg overflow-hidden">
          <iframe
            src={googleMapsUrl}
            width="100%"
            height="100%"
            style={{ border: 0 }}
            allowFullScreen
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            title="Summerhouse Quesada location map"
          />
        </div>
      </div>

      {/* Distances */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Distances</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {locationData.distances.map((item) => (
            <div key={item.place} className="p-4 border border-gray-200 rounded-lg">
              <h3 className="font-medium text-gray-800">{item.place}</h3>
              <p className="text-sm text-gray-500">
                {item.distance} - approximately {item.time} by car
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Getting Here */}
      <div className="p-6 bg-blue-50 rounded-lg">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Getting Here</h2>
        <div className="space-y-4 text-gray-600">
          <div>
            <h3 className="font-medium text-gray-800">By Air</h3>
            <p>
              The nearest airports are Alicante-Elche (ALC) and Murcia-San Javier (RMU).
              Both airports have car rental facilities and are well-connected by highway.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-gray-800">By Car</h3>
            <p>
              From Alicante airport, take the AP-7 motorway south, exit at Crevillente/Quesada,
              and follow signs to Ciudad Quesada. Free parking is available at the property.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-gray-800">From the UK</h3>
            <p>
              Direct flights to Alicante are available from most UK airports with airlines
              including Ryanair, easyJet, and Jet2. Flight time is approximately 2.5 hours.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
