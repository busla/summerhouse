import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'FAQ | Summerhouse Quesada',
  description: 'Frequently asked questions about booking and staying at Summerhouse Quesada vacation rental in Costa Blanca, Spain.',
};

const faqSections = [
  {
    title: 'Booking & Payments',
    questions: [
      {
        q: 'How do I make a booking?',
        a: 'Simply chat with our AI assistant on the homepage. Tell it your preferred dates, and it will check availability, show you the price, and guide you through the booking process. You can also ask it questions about the property and area.',
      },
      {
        q: 'What payment methods do you accept?',
        a: 'We accept major credit and debit cards (Visa, Mastercard, American Express) and PayPal. Payment is processed securely through our booking system.',
      },
      {
        q: 'Is a deposit required?',
        a: 'Yes, we require a €200 security deposit which is held during your stay and refunded within 7 days of checkout, assuming no damage to the property.',
      },
      {
        q: 'What is your cancellation policy?',
        a: 'Cancellations 30+ days before check-in receive a full refund. Cancellations 14-29 days before check-in receive a 50% refund. Cancellations less than 14 days before check-in are non-refundable.',
      },
      {
        q: 'Can I modify my booking?',
        a: 'Yes, subject to availability. Contact us through the booking chat as soon as possible if you need to change your dates. Changes may affect the price depending on seasonal rates.',
      },
    ],
  },
  {
    title: 'Check-in & Check-out',
    questions: [
      {
        q: 'What time is check-in and check-out?',
        a: 'Check-in is from 3:00 PM and check-out is by 10:00 AM. Early check-in or late check-out may be available for an additional €30, subject to availability.',
      },
      {
        q: 'How do I access the property?',
        a: 'We use a secure key lockbox system. You\'ll receive the access code and detailed arrival instructions via email a few days before your check-in date.',
      },
      {
        q: 'Is there parking available?',
        a: 'Yes, there is a free private parking space available at the property for one vehicle.',
      },
      {
        q: 'Can I store luggage before check-in or after check-out?',
        a: 'We don\'t have dedicated luggage storage, but if you\'re arriving early or leaving late, please contact us and we\'ll try to accommodate you if possible.',
      },
    ],
  },
  {
    title: 'Property & Amenities',
    questions: [
      {
        q: 'How many guests can stay?',
        a: 'The property accommodates up to 4 guests. There are 2 bedrooms: one with a double bed and one with twin beds.',
      },
      {
        q: 'Is WiFi available?',
        a: 'Yes, free high-speed WiFi is available throughout the property. Connection details are provided in the welcome information.',
      },
      {
        q: 'Is there air conditioning?',
        a: 'Yes, air conditioning and heating are available in all rooms, included in the rental price.',
      },
      {
        q: 'What\'s in the kitchen?',
        a: 'The kitchen is fully equipped with refrigerator, ceramic hob, microwave, dishwasher, toaster, kettle, coffee maker, and all cookware/utensils you\'ll need.',
      },
      {
        q: 'Are bed linens and towels provided?',
        a: 'Yes, all bed linens and bath towels are provided and freshly laundered. Please bring your own beach towels.',
      },
      {
        q: 'Is there a washing machine?',
        a: 'Yes, there\'s a washing machine available for guest use. Detergent is provided.',
      },
    ],
  },
  {
    title: 'Pool & Outdoor',
    questions: [
      {
        q: 'Is there a pool?',
        a: 'Yes, there\'s access to a lovely community pool just a short walk from the apartment. Sun loungers are available on a first-come basis.',
      },
      {
        q: 'What are the pool opening hours?',
        a: 'The community pool is typically open from 10:00 AM to 8:00 PM during summer months. Hours may vary in other seasons.',
      },
      {
        q: 'Is there outdoor space?',
        a: 'Yes, the property has a private terrace with garden furniture, perfect for al fresco dining. A BBQ grill is also available.',
      },
    ],
  },
  {
    title: 'Policies & Rules',
    questions: [
      {
        q: 'Are pets allowed?',
        a: 'Sorry, pets are not allowed at the property.',
      },
      {
        q: 'Is smoking permitted?',
        a: 'Smoking is not permitted inside the property. You may smoke on the outdoor terrace.',
      },
      {
        q: 'Are parties or events allowed?',
        a: 'No, parties or events are not permitted. The property is in a residential community with quiet hour rules.',
      },
      {
        q: 'Is the property suitable for children?',
        a: 'Yes, the property is family-friendly. However, please note that the community pool area may not be fenced. Children should always be supervised.',
      },
    ],
  },
  {
    title: 'Getting There',
    questions: [
      {
        q: 'What\'s the nearest airport?',
        a: 'Alicante-Elche Airport (ALC) is 45 km away (~40 min drive). Murcia-San Javier Airport (RMU) is 35 km away (~30 min drive). Both have car rental facilities.',
      },
      {
        q: 'Do I need a car?',
        a: 'While not essential, a car is highly recommended to explore the beaches, golf courses, and attractions in the area. The nearest supermarket is a 10-minute walk.',
      },
      {
        q: 'Are there taxis or public transport?',
        a: 'Taxis are available but not always plentiful in the area. There is a bus service but it\'s limited. For convenience, we recommend renting a car.',
      },
    ],
  },
];

export default function FAQPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Frequently Asked Questions</h1>

      <p className="text-gray-600 mb-8">
        Find answers to common questions about Summerhouse Quesada. If you can&apos;t find
        what you&apos;re looking for, feel free to ask our AI assistant on the homepage -
        it&apos;s happy to help!
      </p>

      <div className="space-y-10">
        {faqSections.map((section) => (
          <section key={section.title}>
            <h2 className="text-xl font-semibold text-gray-800 mb-4 pb-2 border-b border-gray-200">
              {section.title}
            </h2>
            <div className="space-y-4">
              {section.questions.map((item, index) => (
                <details
                  key={index}
                  className="group bg-gray-50 rounded-lg"
                >
                  <summary className="flex items-center justify-between cursor-pointer p-4 font-medium text-gray-800 hover:bg-gray-100 rounded-lg">
                    <span>{item.q}</span>
                    <svg
                      className="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </summary>
                  <div className="px-4 pb-4 text-gray-600">
                    {item.a}
                  </div>
                </details>
              ))}
            </div>
          </section>
        ))}
      </div>

      {/* Still have questions */}
      <div className="mt-12 bg-blue-50 rounded-lg p-6 text-center">
        <h2 className="text-xl font-semibold text-gray-800 mb-2">Still have questions?</h2>
        <p className="text-gray-600 mb-4">
          Our AI assistant is available 24/7 to answer your questions about the property,
          availability, local area, and more.
        </p>
        <a
          href="/"
          className="inline-flex items-center gap-2 bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Chat with us
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </a>
      </div>
    </div>
  );
}
