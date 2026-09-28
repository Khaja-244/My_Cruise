const CONTENT = {
  'Terms of Service': {
    intro: 'These terms describe the rules for using my_cruise to discover and book cruise sailings.',
    sections: [
      ['Accounts', 'Keep your account information accurate and protect your login details. You are responsible for activity performed through your account.'],
      ['Cruise bookings', 'A booking is subject to live sailing, cabin and payment availability. Cabin information shown before checkout is an estimate until the server successfully creates a hold.'],
      ['Payment', 'Prices are displayed in USD. The final amount is calculated by the booking service and may include cabin charges, extra-guest charges, port fees and applicable tax. Stripe handles payment details.'],
      ['Schedule changes', 'Cruise operators or partners may change schedules, ports or operating details. Where a material change affects a confirmed booking, my_cruise will communicate the available next steps.'],
      ['Traveler responsibility', 'Travelers are responsible for providing accurate guest information and carrying documents required for their itinerary, including identification or passport documents where applicable.'],
      ['Acceptable use', 'Do not attempt to bypass authentication, manipulate inventory, submit fraudulent bookings, abuse APIs, or interfere with the service.'],
    ],
  },
  'Privacy Policy': {
    intro: 'This page explains, in plain language, how my_cruise uses information needed to operate the booking service.',
    sections: [
      ['Information used', 'The platform may process account details, contact information, guest information, booking details and payment-related status information needed to provide the service.'],
      ['Payments', 'Payment card details are handled by the configured payment provider. my_cruise receives the payment result and relevant transaction references rather than storing raw card credentials in the application database.'],
      ['Service communications', 'Email or push notifications may be used for account verification, password recovery, booking updates, cancellation decisions and refund status.'],
      ['Security', 'Authentication, authorization, password hashing and protected API access are used to reduce unauthorized access. No internet service can guarantee absolute security.'],
      ['Data requests', 'For questions about account information or privacy, use the support channel configured by the operator of this deployment.'],
    ],
  },
  'Refund & Cancellation Policy': {
    intro: 'Cancellation eligibility and refund amounts are determined by the refund policy configured for the cruise. The applicable rule is shown before a cancellation request is submitted.',
    sections: [
      ['How cancellation works', 'Open a confirmed booking, review the refund preview, and submit a cancellation request. An administrator reviews the request against the applicable policy.'],
      ['Refund calculation', 'The system applies the matching number-of-days-before-departure rule, calculates the configured refund percentage, and subtracts any configured flat cancellation fee. The amount cannot exceed the eligible booking amount.'],
      ['Approval and payment', 'When an eligible request is approved, the configured Stripe refund process is initiated. The booking and refund status are updated after the payment provider response is received.'],
      ['Processing time', 'A refund can remain in processing while the payment provider completes the transaction. Bank or card-provider posting time may differ from the application status time.'],
      ['No applicable rule', 'If no active refund policy or matching rule exists, the application will not invent a refund amount; the cancellation request requires administrative handling according to the configured policy.'],
    ],
  },
  FAQ: {
    intro: 'Common questions about the my_cruise booking experience.',
    sections: [
      ['When is a cabin secured?', 'A cabin becomes temporarily held after the server accepts the booking hold. The hold expires automatically if payment is not completed within the configured window.'],
      ['Can two websites sell the same cabin?', 'They can display the same central inventory, but the backend row lock and booking service allow only one successful hold for a cabin at a time.'],
      ['Why did a cabin become unavailable?', 'Another traveler or partner website may have held or booked it, or an administrator may have disabled it. Refreshing availability retrieves the current server state.'],
      ['When is a booking confirmed?', 'A successful payment must be confirmed by the backend payment workflow. The browser does not independently mark a booking as confirmed.'],
    ],
  },
  'Contact & Support': {
    intro: 'Use the support contact configured by the organization operating this my_cruise deployment for booking, payment or partner-integration questions.',
    sections: [
      ['Booking support', 'Include your booking reference, sailing date and a short description of the issue. Do not send full card numbers or passwords.'],
      ['Payment support', 'For payment issues, include the booking reference and payment status shown in the application. Payment-provider transaction details may be required for investigation.'],
      ['Partner integration', 'Partners should include the partner website identifier, endpoint involved and timestamp when reporting an API integration issue.'],
    ],
  },
  'About my_cruise': {
    intro: 'my_cruise is a cruise booking platform designed around live cabin inventory, secure payments and connected partner sales channels.',
    sections: [
      ['Traveler experience', 'Travelers can discover cruises, select sailing dates and cabins, manage bookings and receive booking or cancellation updates.'],
      ['Central inventory', 'The same backend inventory is used by direct traveler bookings and approved partner websites. This is designed to prevent the same cabin from being sold twice across channels.'],
      ['Partner ecosystem', 'Approved partners can manage eligible cruises and use controlled API integrations to present inventory on their own websites.'],
    ],
  },
  'Booking Policy': {
    intro: 'This page explains how cabin holds, occupancy, pricing and confirmation work when you book on my_cruise.',
    sections: [
      ['Cabin holds', 'Selecting one or more cabins creates a temporary hold, not an immediate booking. A countdown shows the time remaining to complete guest details and payment. If the hold expires first, the cabin is released and can be booked by someone else.'],
      ['Occupancy limits', 'Each cabin has a maximum occupancy set by its cabin type. The booking flow will not accept more guests in a cabin than that cabin, or its cabin type, supports.'],
      ['Guest details', 'Every guest on a booking requires a full legal name and the other details requested before payment. This information is used on your e-ticket and should match your travel documents.'],
      ['Pricing shown while booking', 'The price shown while selecting cabins is an estimate covering the cabin fare, extra-guest pricing and any port fees. The final total is calculated by the server at checkout and is the amount actually charged.'],
      ['Confirmation', 'A booking is confirmed only once payment has been verified by the server. A confirmation email and e-ticket become available after the booking status shows Confirmed.'],
      ['Same rules for every channel', 'Direct my_cruise bookings and bookings made through an approved partner website follow the same hold, occupancy and confirmation rules, because both use the same booking service and cabin inventory.'],
    ],
  },
};

export default function Legal({ title, children }) {
  const content = CONTENT[title];
  const sections = content?.sections || [];

  return (
    <div className="container-app py-10 lg:py-16">
      <div className="mx-auto max-w-4xl">
        <p className="eyebrow">my_cruise information</p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-primary sm:text-5xl">{title}</h1>
        <p className="muted mt-4 max-w-3xl leading-7">
          {content?.intro || 'Review the information applicable to your use of the my_cruise platform.'}
        </p>

        <div className="mt-8 space-y-4">
          {children || sections.map(([heading, body]) => (
            <section key={heading} className="card p-6 sm:p-7">
              <h2 className="text-lg font-extrabold text-primary">{heading}</h2>
              <p className="muted mt-2 leading-7">{body}</p>
            </section>
          ))}
        </div>

        <p className="mt-8 text-xs leading-5 text-muted">
          This is project-specific informational content for the my_cruise application. The organization operating a deployment should review and adapt legal wording with appropriate professional advice before public launch.
        </p>
      </div>
    </div>
  );
}
