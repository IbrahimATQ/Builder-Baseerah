import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import DashboardLayout from "@/components/dashboard/DashboardLayout";
import AIVisualization from "@/components/dashboard/AIVisualization";
import FileUploadZone from "@/components/dashboard/FileUploadZone";
import MetricsChart from "@/components/dashboard/MetricsChart";
import AlertSystem from "@/components/dashboard/AlertSystem";
import ChatInterface from "@/components/dashboard/ChatInterface";
import {
  CpuChipIcon,
  ChartBarIcon,
  ClockIcon,
  ArrowTrendingUpIcon,
  UserGroupIcon,
  DocumentIcon,
  ShieldCheckIcon,
  CloudIcon,
  BoltIcon,
  HeartIcon,
  BeakerIcon,
  MagnifyingGlassIcon,
} from "@heroicons/react/24/outline";

const Index = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [isChatMinimized, setIsChatMinimized] = useState(true);
  const [realtimeStats, setRealtimeStats] = useState({
    patientsProcessed: 1247,
    aiAccuracy: 94.7,
    responseTime: 0.3,
    activeModels: 12,
  });

  useEffect(() => {
    // Simulate real-time data updates
    const interval = setInterval(() => {
      setRealtimeStats((prev) => ({
        ...prev,
        patientsProcessed:
          prev.patientsProcessed + Math.floor(Math.random() * 3),
        aiAccuracy: Math.max(
          90,
          Math.min(99, prev.aiAccuracy + (Math.random() - 0.5) * 0.5),
        ),
        responseTime: Math.max(
          0.1,
          Math.min(1.0, prev.responseTime + (Math.random() - 0.5) * 0.1),
        ),
      }));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const handleFileUpload = (files: File[]) => {
    setIsProcessing(true);
    setTimeout(() => setIsProcessing(false), 3000);
  };

  const toggleChat = () => {
    setIsChatMinimized(!isChatMinimized);
  };

  const kpiMetrics = [
    {
      title: "AI Models Active",
      value: realtimeStats.activeModels,
      unit: "models",
      change: "+2",
      trend: "up",
      icon: CpuChipIcon,
      color: "medical-blue",
    },
    {
      title: "Patients Processed",
      value: realtimeStats.patientsProcessed.toLocaleString(),
      unit: "today",
      change: "+15%",
      trend: "up",
      icon: UserGroupIcon,
      color: "medical-green",
    },
    {
      title: "AI Accuracy",
      value: realtimeStats.aiAccuracy.toFixed(1),
      unit: "%",
      change: "+0.3%",
      trend: "up",
      icon: ArrowTrendingUpIcon,
      color: "medical-purple",
    },
    {
      title: "Response Time",
      value: realtimeStats.responseTime.toFixed(1),
      unit: "seconds",
      change: "-0.1s",
      trend: "down",
      icon: ClockIcon,
      color: "medical-teal",
    },
  ];

  const enterpriseMetrics = [
    {
      title: "Data Processing",
      value: "2.4TB",
      description: "Processed in the last 24 hours",
      icon: DocumentIcon,
      color: "medical-blue",
    },
    {
      title: "Security Compliance",
      value: "100%",
      description: "HIPAA & SOC2 compliant",
      icon: ShieldCheckIcon,
      color: "medical-green",
    },
    {
      title: "Cloud Infrastructure",
      value: "99.9%",
      description: "Uptime across all regions",
      icon: CloudIcon,
      color: "medical-purple",
    },
    {
      title: "Performance Score",
      value: "A+",
      description: "Enterprise scalability rating",
      icon: BoltIcon,
      color: "medical-amber",
    },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Hero Section */}
        <motion.div
          className="text-center py-8"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          <h1 className="text-4xl md:text-6xl font-bold mb-4">
            <span className="gradient-text">Next-Generation</span>
            <br />
            <span className="text-foreground">AI Medical Diagnostics</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Revolutionizing healthcare with artificial intelligence-powered lab
            result interpretation, real-time monitoring, and predictive
            analytics
          </p>

          {/* AI Processing Status */}
          <motion.div
            className="mt-8 inline-flex items-center gap-3 glass-card p-4 rounded-full"
            animate={{
              boxShadow: [
                "0 0 20px rgba(59, 130, 246, 0.3)",
                "0 0 40px rgba(59, 130, 246, 0.5)",
                "0 0 20px rgba(59, 130, 246, 0.3)",
              ],
            }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            <div className="w-3 h-3 rounded-full bg-medical-green animate-neural-pulse" />
            <span className="text-sm text-medical-green font-medium">
              AI Neural Networks Online
            </span>
            <div className="flex gap-1">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="w-1 h-4 bg-medical-blue rounded-full animate-pulse"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          </motion.div>
        </motion.div>

        {/* KPI Metrics */}
        <motion.div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          {kpiMetrics.map((metric, index) => (
            <motion.div
              key={metric.title}
              className="glass-enhanced p-6 rounded-2xl"
              whileHover={{ scale: 1.05, rotateY: 5 }}
              transition={{ duration: 0.3 }}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ transitionDelay: `${index * 0.1}s` }}
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`p-3 rounded-xl bg-${metric.color}/20`}>
                  <metric.icon className={`w-6 h-6 text-${metric.color}`} />
                </div>
                <div
                  className={`text-xs px-2 py-1 rounded-full ${
                    metric.trend === "up"
                      ? "bg-medical-green/20 text-medical-green"
                      : "bg-medical-blue/20 text-medical-blue"
                  }`}
                >
                  {metric.change}
                </div>
              </div>
              <div className="text-2xl font-bold text-foreground mb-1">
                {metric.value}
                <span className="text-sm text-muted-foreground ml-1">
                  {metric.unit}
                </span>
              </div>
              <div className="text-sm text-muted-foreground">
                {metric.title}
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Main Dashboard Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Left Column */}
          <div className="xl:col-span-2 space-y-6">
            {/* AI Visualization */}
            <motion.div
              className="glass-enhanced rounded-2xl p-6"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
            >
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-semibold text-foreground mb-2">
                    AI Neural Network
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Real-time artificial intelligence processing visualization
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-xs text-medical-green">
                    Model: v2.1.3
                  </div>
                  <div className="w-2 h-2 rounded-full bg-medical-green animate-neural-pulse" />
                </div>
              </div>
              <AIVisualization
                isProcessing={isProcessing}
                confidence={Math.floor(realtimeStats.aiAccuracy)}
                className="h-64"
              />
            </motion.div>

            {/* Metrics Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <MetricsChart
                type="line"
                title="Vital Signs Monitoring"
                className="h-96"
              />
              <MetricsChart
                type="bar"
                title="Lab Results Summary"
                className="h-96"
              />
            </div>

            {/* File Upload Zone */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
            >
              <div className="mb-4">
                <h3 className="text-xl font-semibold text-foreground mb-2">
                  AI-Powered Data Analysis
                </h3>
                <p className="text-sm text-muted-foreground">
                  Upload medical data for instant AI interpretation and insights
                </p>
              </div>
              <FileUploadZone
                onFileUpload={handleFileUpload}
                acceptedFormats={[".pdf", ".csv", ".xlsx", ".json", ".dicom"]}
                maxSize={50 * 1024 * 1024} // 50MB
              />
            </motion.div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Alert System */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
            >
              <AlertSystem maxVisible={4} />
            </motion.div>

            {/* Enterprise Features */}
            <motion.div
              className="glass-enhanced rounded-2xl p-6"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.7 }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Enterprise Ready
              </h3>
              <div className="space-y-4">
                {enterpriseMetrics.map((metric, index) => (
                  <div
                    key={metric.title}
                    className="flex items-center gap-3 p-3 rounded-xl hover:bg-medical-glass/30 transition-colors"
                  >
                    <div className={`p-2 rounded-lg bg-${metric.color}/20`}>
                      <metric.icon className={`w-4 h-4 text-${metric.color}`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-foreground">
                          {metric.title}
                        </span>
                        <span
                          className={`text-sm font-bold text-${metric.color}`}
                        >
                          {metric.value}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {metric.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Quick Actions */}
            <motion.div
              className="glass-enhanced rounded-2xl p-6"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.8 }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Quick Actions
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {[
                  {
                    label: "Lab Analysis",
                    icon: BeakerIcon,
                    color: "medical-blue",
                  },
                  {
                    label: "Patient Search",
                    icon: MagnifyingGlassIcon,
                    color: "medical-teal",
                  },
                  {
                    label: "Vital Monitoring",
                    icon: HeartIcon,
                    color: "medical-red",
                  },
                  {
                    label: "AI Insights",
                    icon: CpuChipIcon,
                    color: "medical-purple",
                  },
                ].map((action) => (
                  <button
                    key={action.label}
                    className={`p-4 rounded-xl glass-card hover:bg-${action.color}/10 transition-all duration-200 group`}
                  >
                    <action.icon
                      className={`w-6 h-6 text-${action.color} mb-2 group-hover:scale-110 transition-transform`}
                    />
                    <div className="text-xs font-medium text-foreground">
                      {action.label}
                    </div>
                  </button>
                ))}
              </div>
            </motion.div>
          </div>
        </div>

        {/* Innovation Showcase */}
        <motion.div
          className="glass-enhanced rounded-2xl p-8 text-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.0 }}
        >
          <h2 className="text-2xl font-bold text-foreground mb-4">
            Powered by Advanced Machine Learning
          </h2>
          <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
            Our proprietary neural networks process over 2.4TB of medical data
            daily, delivering insights with 94.7% accuracy and sub-second
            response times.
          </p>
          <div className="flex justify-center items-center gap-8">
            {[
              { label: "Deep Learning", value: "12 Models" },
              { label: "Processing Speed", value: "0.3s avg" },
              { label: "Data Security", value: "HIPAA+" },
              { label: "Global Reach", value: "50+ Countries" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <div className="text-2xl font-bold gradient-text mb-1">
                  {stat.value}
                </div>
                <div className="text-xs text-muted-foreground">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Floating Chat Interface */}
      <ChatInterface
        isMinimized={isChatMinimized}
        onToggle={toggleChat}
        className={
          isChatMinimized
            ? "fixed bottom-4 right-4 z-50"
            : "fixed bottom-4 right-4 w-96 z-50"
        }
      />
    </DashboardLayout>
  );
};

export default Index;
