import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Contact | Summerhouse Quesada',
  description: 'Get in touch with Summerhouse Quesada. Contact us for booking inquiries, questions, or assistance with your stay.',
};

const contactMethods = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    title: 'AI Assistant',
    description: 'Get instant answers 24/7',
    action: 'Chat Now',
    href: '/',
    primary: true,
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    title: 'Email',
    description: 'hello@summerhousequesada.com',
    action: 'Send Email',
    href: 'mailto:hello@summerhousequesada.com',
  },
];

const emergencyContacts = [
  { name: 'Local Emergency Services', number: '112', description: 'Police, Fire, Ambulance' },
  { name: 'Property Manager', number: '+34 XXX XXX XXX', description: 'Urgent property issues' },
  { name: 'Nearest Hospital', number: 'Hospital Universitario de Torrevieja', description: '15 min drive' },
];

export default function ContactPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Contact Us</h1>

      <p className="text-gray-600 mb-8 text-lg">
        We&apos;re here to help! Whether you have questions about booking, need assistance
        during your stay, or just want to say hello, we&apos;d love to hear from you.
      </p>

      {/* Contact Methods */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
        {contactMethods.map((method) => (
          <div
            key={method.title}
            className={`p-6 rounded-lg border ${
              method.primary
                ? 'bg-blue-50 border-blue-200'
                : 'bg-white border-gray-200'
            }`}
          >
            <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-4 ${
              method.primary ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
            }`}>
              {method.icon}
            </div>
            <h2 className="text-lg font-semibold text-gray-800 mb-1">{method.title}</h2>
            <p className="text-gray-600 mb-4">{method.description}</p>
            <a
              href={method.href}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                method.primary
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {method.action}
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </a>
          </div>
        ))}
      </div>

      {/* Response Times */}
      <div className="mb-12 p-6 bg-yellow-50 border border-yellow-200 rounded-lg">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Response Times</h2>
        <ul className="space-y-2 text-gray-700">
          <li className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            <strong>AI Assistant:</strong> Instant - available 24/7
          </li>
          <li className="flex items-center gap-2">
            <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
            <strong>Email:</strong> Within 24 hours (usually faster)
          </li>
        </ul>
        <p className="text-sm text-gray-600 mt-3">
          For urgent matters during your stay, please contact our property manager directly.
        </p>
      </div>

      {/* Before You Contact Us */}
      <div className="mb-12">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Before You Contact Us</h2>
        <p className="text-gray-600 mb-4">
          You might find the answer you&apos;re looking for in these resources:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href="/faq"
            className="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <h3 className="font-medium text-gray-800 mb-1">FAQ</h3>
            <p className="text-sm text-gray-600">Common questions answered</p>
          </a>
          <a
            href="/about"
            className="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <h3 className="font-medium text-gray-800 mb-1">About</h3>
            <p className="text-sm text-gray-600">Property details & amenities</p>
          </a>
          <a
            href="/area-guide"
            className="p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <h3 className="font-medium text-gray-800 mb-1">Area Guide</h3>
            <p className="text-sm text-gray-600">Local attractions & tips</p>
          </a>
        </div>
      </div>

      {/* Emergency Contacts */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-red-800 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          Emergency Contacts
        </h2>
        <p className="text-gray-700 mb-4">
          For emergencies during your stay, please use these contacts:
        </p>
        <div className="space-y-3">
          {emergencyContacts.map((contact) => (
            <div key={contact.name} className="flex flex-col md:flex-row md:items-center gap-1 md:gap-4">
              <span className="font-medium text-gray-800 md:min-w-[200px]">{contact.name}</span>
              <span className="text-red-700 font-mono">{contact.number}</span>
              <span className="text-sm text-gray-500">({contact.description})</span>
            </div>
          ))}
        </div>
      </div>

      {/* Location Quick Link */}
      <div className="mt-8 text-center">
        <p className="text-gray-600 mb-2">Need directions?</p>
        <a
          href="/location"
          className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-800"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          View our location & map
        </a>
      </div>
    </div>
  );
}
