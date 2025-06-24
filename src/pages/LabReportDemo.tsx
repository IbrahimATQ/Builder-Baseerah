import React from "react";
import { motion } from "framer-motion";
import { ArrowLeftIcon, CheckCircleIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";

const LabReportDemo = () => {
  const navigate = useNavigate();

  return (
    <div
      className="min-h-screen bg-white text-black"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      {/* Back to Dashboard Button */}
      <div className="p-6">
        <motion.button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 mb-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <ArrowLeftIcon className="w-4 h-4" />
          Back to Dashboard
        </motion.button>
      </div>

      {/* A4 Document Container */}
      <div className="flex justify-center">
        <motion.div
          className="bg-white"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          style={{
            width: "816px",
            minHeight: "1056px", // A4 height
            paddingLeft: "48px",
            paddingRight: "48px",
            paddingTop: "64px",
            paddingBottom: "64px",
            boxShadow:
              "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
          }}
        >
          {/* Header */}
          <div className="border-b border-blue-600 pb-6 mb-8">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                  <span className="text-white font-bold text-sm">B</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-blue-600">
                    Baseerah Technologies
                  </h1>
                  <p className="text-gray-600 text-sm">
                    AI-Powered Lab Interpretation
                  </p>
                </div>
              </div>
              <div className="text-right text-sm" style={{ color: "#111827" }}>
                <div className="font-semibold">Patient ID #12847</div>
                <div className="text-gray-600">Date 24 Jun 2025</div>
                <div className="text-gray-600">Generated 7:16 PM</div>
              </div>
            </div>
          </div>

          {/* Patient Demographics */}
          <div className="mb-8">
            <h2
              className="text-xl font-semibold mb-4"
              style={{ color: "#111827" }}
            >
              Patient Demographics
            </h2>
            <div className="grid grid-cols-2 gap-8">
              <div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: "#374151" }}>
                    Name:
                  </span>
                  <span className="ml-2 font-normal">Ahmed Al-Mansouri</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: "#374151" }}>
                    Age:
                  </span>
                  <span className="ml-2 font-normal">45 years</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: "#374151" }}>
                    Gender:
                  </span>
                  <span className="ml-2 font-normal">Male</span>
                </div>
              </div>
              <div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: "#374151" }}>
                    MRN:
                  </span>
                  <span className="ml-2 font-normal">MRN-2024-12847</span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: "#374151" }}>
                    Collection Date:
                  </span>
                  <span className="ml-2 font-normal">
                    {new Date().toLocaleDateString()}
                  </span>
                </div>
                <div className="mb-3">
                  <span className="font-bold" style={{ color: "#374151" }}>
                    Ordering Physician:
                  </span>
                  <span className="ml-2 font-normal">Dr. Sarah Al-Zahra</span>
                </div>
              </div>
            </div>
          </div>

          {/* Laboratory Results Table */}
          <div className="mb-8">
            <h2
              className="text-xl font-semibold mb-4"
              style={{ color: "#111827" }}
            >
              Laboratory Results
            </h2>
            <table className="w-full border-collapse border border-gray-300">
              <thead>
                <tr style={{ backgroundColor: "#1E3A8A" }}>
                  <th className="border border-gray-300 p-3 text-left font-semibold text-white">
                    Test
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Result
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Range
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Status
                  </th>
                  <th className="border border-gray-300 p-3 text-center font-semibold text-white">
                    Units
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-gray-300 p-3 font-medium">
                    HbA1c
                  </td>
                  <td className="border border-gray-300 p-3 text-center font-mono">
                    6.2
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    4.0 - 5.6
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    <span
                      className="px-3 py-1 rounded-full text-white text-sm font-medium"
                      style={{ backgroundColor: "#F59E0B" }}
                    >
                      High
                    </span>
                  </td>
                  <td className="border border-gray-300 p-3 text-center">%</td>
                </tr>
                <tr className="bg-gray-50">
                  <td className="border border-gray-300 p-3 font-medium">
                    LDL Cholesterol
                  </td>
                  <td className="border border-gray-300 p-3 text-center font-mono">
                    160
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    &lt; 100
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    <span
                      className="px-3 py-1 rounded-full text-white text-sm font-medium"
                      style={{ backgroundColor: "#EF4444" }}
                    >
                      Critical
                    </span>
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    mg/dL
                  </td>
                </tr>
                <tr>
                  <td className="border border-gray-300 p-3 font-medium">
                    Creatinine
                  </td>
                  <td className="border border-gray-300 p-3 text-center font-mono">
                    2.4
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    0.6 - 1.2
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    <span
                      className="px-3 py-1 rounded-full text-white text-sm font-medium"
                      style={{ backgroundColor: "#EF4444" }}
                    >
                      Critical
                    </span>
                  </td>
                  <td className="border border-gray-300 p-3 text-center">
                    mg/dL
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* AI Clinical Interpretation */}
          <div className="mb-8">
            <div
              className="p-6 rounded-lg border-l-4"
              style={{
                borderLeftColor: "#3B82F6",
                backgroundColor: "#F8FAFC",
              }}
            >
              <div className="flex items-center justify-between mb-4">
                <h2
                  className="text-xl font-semibold"
                  style={{ color: "#111827" }}
                >
                  AI Clinical Interpretation
                </h2>
                <div
                  className="px-3 py-1 rounded-full text-white text-sm font-medium"
                  style={{ backgroundColor: "#3B82F6" }}
                >
                  AI Confidence 94%
                </div>
              </div>

              <div className="space-y-6">
                {/* Integrated Clinical Context */}
                <div>
                  <h3 className="font-bold mb-3" style={{ color: "#111827" }}>
                    Integrated Clinical Context
                  </h3>
                  <div className="bg-gray-100 p-4 rounded-lg border-l-2 border-gray-400">
                    <p className="text-sm text-gray-600 italic mb-1">
                      Clinical Note Extract:
                    </p>
                    <p className="text-gray-700">
                      "45-year-old male, BMI 31 kg/m², hypertension on
                      lisinopril, smoker (15 pack-years), presents for routine
                      metabolic panel."
                    </p>
                  </div>
                </div>

                {/* Result-Linked Analysis */}
                <div>
                  <h3 className="font-bold mb-3" style={{ color: "#111827" }}>
                    Result-Linked Analysis
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <span className="font-mono text-sm bg-yellow-100 px-2 py-1 rounded">
                        HbA1c 6.2%
                      </span>
                      <p className="text-gray-700 text-sm">
                        → "Consistent with ADA 'pre-diabetes' criteria; aligns
                        with prior fasting glucose (112 mg/dL)."
                      </p>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="font-mono text-sm bg-red-100 px-2 py-1 rounded">
                        LDL 160 mg/dL
                      </span>
                      <p className="text-gray-700 text-sm">
                        → "ASCVD 10-yr risk now ≥ 15%. Intensify lipid-lowering
                        therapy."
                      </p>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="font-mono text-sm bg-red-100 px-2 py-1 rounded">
                        Creatinine 2.4 mg/dL
                      </span>
                      <p className="text-gray-700 text-sm">
                        → "eGFR ≈ 32 mL/min/1.73 m² (CKD-3b). Possible diabetic
                        nephropathy."
                      </p>
                    </div>
                  </div>
                </div>

                {/* Evidence-Based Recommendations */}
                <div>
                  <h3 className="font-bold mb-3" style={{ color: "#111827" }}>
                    Evidence-Based Recommendations
                  </h3>
                  <ol className="text-gray-700 space-y-2">
                    <li className="flex items-start">
                      <span className="mr-3 font-bold">1.</span>
                      Start high-intensity statin; target LDL &lt; 70 mg/dL.
                    </li>
                    <li className="flex items-start">
                      <span className="mr-3 font-bold">2.</span>
                      Initiate metformin 500 mg BID after nephrology clearance.
                    </li>
                    <li className="flex items-start">
                      <span className="mr-3 font-bold">3.</span>
                      Refer to Nephrology (auto-booked below) for renal work-up
                      + ACE inhibitor optimization.
                    </li>
                    <li className="flex items-start">
                      <span className="mr-3 font-bold">4.</span>
                      Lifestyle: DASH diet, smoking cessation, 150 min/week
                      moderate exercise.
                    </li>
                  </ol>
                </div>
              </div>
            </div>
          </div>

          {/* Auto-Referral Panel */}
          <div className="mb-8">
            <div
              className="p-4 rounded-lg flex items-center gap-3"
              style={{ backgroundColor: "#DBEAFE" }}
            >
              <CheckCircleIcon className="w-6 h-6 text-blue-600 flex-shrink-0" />
              <div>
                <div className="font-semibold text-blue-900">
                  🚀 Referral Booked ➜ Nephrology
                </div>
                <div className="text-blue-700 text-sm">
                  Appointment: 04 Jul 2025 • 10:00 AM • KFSH, Clinic B
                </div>
              </div>
            </div>
          </div>

          {/* What do these results mean for me? - Doctor-tone */}
          <div className="mb-8">
            <div
              className="p-6 rounded-lg"
              style={{
                backgroundColor: "#F8FAFC",
                borderLeft: "4px solid #6B7280",
              }}
            >
              <h2
                className="text-xl font-semibold mb-4"
                style={{ color: "#111827" }}
              >
                What do these results mean for me?
              </h2>
              <p className="text-gray-700 leading-relaxed">
                These findings place the patient at high cardiometabolic risk
                driven by combined pre-diabetes, severe dyslipidemia, and
                reduced renal function. Early pharmacologic intervention plus
                multidisciplinary follow-up is warranted to prevent progression
                to overt diabetes, myocardial infarction, and end-stage kidney
                disease.
              </p>
            </div>
          </div>

          {/* Intelligent Patient Report Sent */}
          <div className="mb-8">
            <div
              className="p-6 rounded-xl border-2 border-green-200"
              style={{ backgroundColor: "#F0FDF4" }}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <h2
                    className="text-xl font-semibold"
                    style={{ color: "#111827" }}
                  >
                    Intelligent Patient Report Sent 📨
                  </h2>
                  <span className="px-2 py-1 bg-green-600 text-white text-xs rounded-full">
                    AI-Personalized
                  </span>
                </div>
                <div className="text-right text-sm text-gray-600">
                  <div>📱 Baseerah Mobile App</div>
                  <div>🕒 24 Jun 2025, 7:18 PM</div>
                  <div>✅ Read Receipt: 7:23 PM</div>
                </div>
              </div>

              {/* Personalized Summary Section */}
              <div className="space-y-4">
                <div className="bg-white p-5 rounded-lg border border-green-100">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-blue-600 font-semibold">
                      🧠 AI-Generated Personalized Summary
                    </span>
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                      Based on your profile
                    </span>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    {/* English Version */}
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <div className="text-sm font-medium text-blue-600 mb-3 flex items-center gap-2">
                        🇺🇸 ENGLISH REPORT
                        <span className="text-xs bg-blue-200 px-2 py-0.5 rounded">
                          Tailored for you
                        </span>
                      </div>
                      <div className="space-y-3 text-gray-700 text-sm leading-relaxed">
                        <p>
                          <strong>Hello Ahmed,</strong>
                        </p>
                        <p>
                          Your recent blood tests show some areas that need
                          attention, but the good news is that with the right
                          steps, you can improve your health significantly.
                        </p>

                        <div className="bg-white p-3 rounded border-l-4 border-yellow-400">
                          <p>
                            <strong>🍬 Blood Sugar (HbA1c): 6.2%</strong>
                            <br />
                            Picture your bloodstream as a bustling city, and
                            sugar molecules as delivery trucks. For the past 3
                            months, there have been too many trucks on the
                            roads, causing mild traffic jams. You're at the
                            "amber zone" - not a crisis, but your body's traffic
                            control system is saying "slow down the sugar
                            deliveries!"
                          </p>
                        </div>

                        <div className="bg-white p-3 rounded border-l-4 border-red-400">
                          <p>
                            <strong>❤️ Cholesterol (LDL): 160 mg/dL</strong>
                            <br />
                            Imagine your arteries as pristine mountain rivers.
                            The "bad" cholesterol is like sediment building up
                            on the riverbed - too much accumulation (160 vs.
                            ideal &lt;100) could eventually block the flow. We
                            need to clear these waterways before they become
                            dams.
                          </p>
                        </div>

                        <div className="bg-white p-3 rounded border-l-4 border-red-400">
                          <p>
                            <strong>🫘 Kidney Function: Needs attention</strong>
                            <br />
                            Your kidneys are like sophisticated water
                            purification plants, but they're working at reduced
                            capacity. Think of them as having clogged filters
                            that need expert maintenance. The good news? We've
                            already scheduled you with the best "engineers"
                            (nephrologists) to assess and optimize your
                            filtration system.
                          </p>
                        </div>

                        <div className="bg-green-50 p-3 rounded">
                          <p>
                            <strong>🎯 Your Action Plan:</strong>
                          </p>
                          <ul className="mt-2 space-y-1 text-xs">
                            <li>
                              • 🚭 <strong>Stop smoking</strong> - this is the
                              #1 priority for your health
                            </li>
                            <li>
                              • 🥗 <strong>DASH diet</strong> - we'll send you a
                              personalized meal plan
                            </li>
                            <li>
                              • 🚶‍♂️ <strong>Walk 30 min daily</strong> - start
                              with 10 minutes if needed
                            </li>
                            <li>
                              • 💊 <strong>New medications</strong> - your
                              doctor will discuss these with you
                            </li>
                            <li>
                              • 📅 <strong>Nephrology visit</strong> - July 4th
                              at 10:00 AM
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>

                    {/* Arabic Version */}
                    <div className="p-4 bg-teal-50 rounded-lg" dir="rtl">
                      <div className="text-sm font-medium text-teal-600 mb-3 flex items-center gap-2 justify-end">
                        <span className="text-xs bg-teal-200 px-2 py-0.5 rounded">
                          مُخصص لك
                        </span>
                        🇸🇦 التقرير العربي
                      </div>
                      <div className="space-y-3 text-gray-700 text-sm leading-relaxed">
                        <p>
                          <strong>أهلاً أحمد،</strong>
                        </p>
                        <p>
                          تحاليل دمك الأخيرة تُظهر بعض النقاط التي تحتاج انتباه،
                          لكن الخبر الجيد أنه بالخطوات الصحيحة، يمكنك تحسين صحتك
                          بشكل كبير.
                        </p>

                        <div className="bg-white p-3 rounded border-r-4 border-yellow-400">
                          <p>
                            <strong>🍬 السكر التراكمي: 6.2%</strong>
                            <br />
                            تصوّر دمك كنهرٍ يجري، وجزيئات السكر كقوارب صغيرة
                            تُبحر فيه. خلال الأشهر الثلاثة الماضية، كان هناك
                            قوارب سكر أكثر من المعتاد تُبحر في نهرك. أنت في
                            "المنطقة البرتقالية" - ليست عاصفة، لكن ربّان النهر
                            (جسدك) يقول: "أبطئ حركة قوارب السكر!"
                          </p>
                        </div>

                        <div className="bg-white p-3 rounded border-r-4 border-red-400">
                          <p>
                            <strong>❤️ الكوليسترول الضار: 160</strong>
                            <br />
                            تخيّل شرايينك كطرق سريعة نظيفة، والكوليسترول "الضار"
                            كالرمال التي تتراكم على جوانب الطريق. لديك رمال أكثر
                            من المطلوب (160 بدلاً من أقل من 100)، وقد تُبطئ حركة
                            المرور إذا لم نُنظفها.
                          </p>
                        </div>

                        <div className="bg-white p-3 rounded border-r-4 border-red-400">
                          <p>
                            <strong>🫘 وظائف الكلى: تحتاج انتباه</strong>
                            <br />
                            كليتاك مثل محطتان متطورتان لتنقية المياه، لكنهما
                            تعملان بطاقة أقل من المعتاد. تصورهما كمرشحات تحتاج
                            صيانة من خبراء. الخبر الجيد؟ حجزنا لك موعداً مع أفضل
                            "المهندسين" (أطباء الكلى) لفحص وتحسين نظام التنقية.
                          </p>
                        </div>

                        <div className="bg-green-50 p-3 rounded">
                          <p>
                            <strong>🎯 خطة العلاج:</strong>
                          </p>
                          <ul className="mt-2 space-y-1 text-xs">
                            <li>
                              • 🚭 <strong>توقف عن التدخين</strong> - هذا
                              الأولوية الأولى لصحتك
                            </li>
                            <li>
                              • 🥗 <strong>حمية DASH</strong> - سنرسل لك خطة
                              وجبات مُخصصة
                            </li>
                            <li>
                              • 🚶‍♂️ <strong>امشِ 30 دقيقة يومياً</strong> - ابدأ
                              بـ10 دقائق إن احتجت
                            </li>
                            <li>
                              • 💊 <strong>أدوية جديدة</strong> - طبيبك سيناقشها
                              معك
                            </li>
                            <li>
                              • 📅 <strong>زيارة أخصائي الكلى</strong> - 4 يوليو
                              الساعة 10:00 صباحاً
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Smart Features Section */}
                <div className="bg-white p-4 rounded-lg border border-gray-200">
                  <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
                    🤖 Smart Report Features
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="text-center p-2 bg-blue-50 rounded">
                      <div className="font-medium text-blue-700">
                        📊 Trend Analysis
                      </div>
                      <div className="text-gray-600">vs. 3 months ago</div>
                    </div>
                    <div className="text-center p-2 bg-green-50 rounded">
                      <div className="font-medium text-green-700">
                        🎯 Risk Score
                      </div>
                      <div className="text-gray-600">Moderate → Low</div>
                    </div>
                    <div className="text-center p-2 bg-purple-50 rounded">
                      <div className="font-medium text-purple-700">
                        📱 App Integration
                      </div>
                      <div className="text-gray-600">Daily reminders</div>
                    </div>
                    <div className="text-center p-2 bg-orange-50 rounded">
                      <div className="font-medium text-orange-700">
                        👨‍⚕️ Next Steps
                      </div>
                      <div className="text-gray-600">Auto-scheduled</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions Section */}
          <div className="mb-8">
            <div className="flex gap-4">
              <button className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">
                🔄 Re-generate in Arabic-only
              </button>
              <button className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors">
                📈 View Trend Graphs
              </button>
            </div>
          </div>

          {/* Digital Access Footer */}
          <div className="mb-8">
            <div className="flex items-center gap-6">
              <div
                className="w-18 h-18 border-2 border-dashed border-gray-400 rounded-lg flex items-center justify-center"
                style={{ width: "72px", height: "72px" }}
              >
                <div className="text-4xl">⚏</div>
              </div>
              <div>
                <h3 className="font-bold mb-1" style={{ color: "#111827" }}>
                  Scan to view full history & trends
                </h3>
                <p className="text-sm text-gray-600">
                  Access complete medical records, trending data, and detailed
                  AI analysis reports through our secure patient portal.
                </p>
              </div>
            </div>
          </div>

          {/* Page Footer */}
          <div className="border-t border-gray-300 pt-4">
            <div className="text-center text-xs text-gray-500 mb-2">
              Generated by Baseerah AI | HIPAA & SFDA SaMD Ready | Report ID
              RPT-1750781784537
            </div>
            <div
              className="border-t pt-2 text-center text-sm text-gray-600"
              style={{ borderColor: "#E5E7EB" }}
            >
              Page 1 of 1
            </div>
          </div>
        </motion.div>
      </div>

      {/* Print Styles */}
      <style>{`
        @media print {
          body { margin: 0; }
          .p-6 { display: none; }
          .bg-white { box-shadow: none !important; }
        }
      `}</style>
    </div>
  );
};

export default LabReportDemo;
