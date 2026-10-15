const projectData = [
  {
    id: "ecommerce",
    name: "E-Commerce",
    initials: "EC",
    color: "blue",
    services: ["payment-api", "order-service", "checkout-service"],
    totalLogs: 128,
    errors: 12,
    warnings: 24,
    incidents: 3,
  },
  {
    id: "hr-portal",
    name: "HR Portal",
    initials: "HR",
    color: "purple",
    services: ["auth-service", "employee-api"],
    totalLogs: 86,
    errors: 4,
    warnings: 9,
    incidents: 1,
  },
  {
    id: "banking",
    name: "Banking",
    initials: "BK",
    color: "green",
    services: ["transfer-api", "ledger-service"],
    totalLogs: 214,
    errors: 7,
    warnings: 16,
    incidents: 2,
  },
];

const serviceData = {
  "payment-api": {
    id: "payment-api",
    name: "Payment API",
    projectId: "ecommerce",
    analysis: {
      severity: "CRITICAL",
      title: "Database Connection Failure",
      summary:
        "Repeated database connection failures are causing payment requests to fail.",
      rootCause:
        "Database connection pool exhaustion or database unavailability.",
      impact: "Payment transactions may fail or experience delays.",
      recommendations: [
        "Check database availability.",
        "Inspect connection pool usage.",
        "Review recent database/network changes.",
      ],
      confidence: 94,
      detected: "2m ago",
    },
    logs: [
      { time: "12:31:42", level: "ERROR", message: "Database connection timeout" },
      { time: "12:31:40", level: "WARN", message: "Retry attempt 3/3" },
      { time: "12:31:35", level: "INFO", message: "Payment request received" },
      { time: "12:31:28", level: "ERROR", message: "Connection pool limit reached" },
      { time: "12:31:21", level: "INFO", message: "Health check completed" },
    ],
    incidents: [
      {
        id: "payment-db",
        severity: "CRITICAL",
        title: "Payment Database Failure",
        serviceId: "payment-api",
        timeAgo: "2 minutes ago",
        status: "Investigating",
        analysisTitle: "Database Connection Failure",
      },
      {
        id: "payment-retries",
        severity: "HIGH",
        title: "Payment Retry Spike",
        serviceId: "payment-api",
        timeAgo: "8 minutes ago",
        status: "Monitoring",
        analysisTitle: "Database Connection Failure",
      },
      {
        id: "order-queue",
        severity: "HIGH",
        title: "Order Processing Delays",
        serviceId: "order-service",
        timeAgo: "6 minutes ago",
        status: "Investigating",
        analysisTitle: "Order Processing Delays",
      },
    ],
  },
  "order-service": {
    id: "order-service",
    name: "Order Service",
    projectId: "ecommerce",
    analysis: {
      severity: "HIGH",
      title: "Order Processing Delays",
      summary:
        "A growing queue of order events is slowing order confirmation for customers.",
      rootCause:
        "The order worker is processing events slower than the incoming queue rate.",
      impact: "Customers may see delayed order confirmations and status updates.",
      recommendations: [
        "Inspect the order queue depth and consumer lag.",
        "Check worker CPU and memory utilization.",
        "Review recent event volume or deployment changes.",
      ],
      confidence: 89,
      detected: "6m ago",
    },
    logs: [
      { time: "12:31:42", level: "WARN", message: "Order queue depth above threshold" },
      { time: "12:31:40", level: "INFO", message: "Order event queued for processing" },
      { time: "12:31:35", level: "ERROR", message: "Worker response exceeded 5s" },
      { time: "12:31:28", level: "INFO", message: "Order #10482 processing started" },
      { time: "12:31:21", level: "WARN", message: "Consumer lag at 1,204 messages" },
    ],
    incidents: [
      {
        id: "order-queue",
        severity: "HIGH",
        title: "Order Processing Delays",
        serviceId: "order-service",
        timeAgo: "6 minutes ago",
        status: "Investigating",
        analysisTitle: "Order Processing Delays",
      },
    ],
  },
  "checkout-service": {
    id: "checkout-service",
    name: "Checkout Service",
    projectId: "ecommerce",
    analysis: {
      severity: "MEDIUM",
      title: "Elevated Checkout Latency",
      summary:
        "Checkout responses are slower than usual, with intermittent upstream timeouts.",
      rootCause:
        "An upstream inventory request is adding latency to checkout transactions.",
      impact: "Some customers may experience a slower checkout flow.",
      recommendations: [
        "Check inventory service response times.",
        "Review recent latency across checkout dependencies.",
        "Compare current checkout traffic with baseline.",
      ],
      confidence: 86,
      detected: "11m ago",
    },
    logs: [
      { time: "12:31:42", level: "WARN", message: "Checkout response time at 2.4s" },
      { time: "12:31:40", level: "INFO", message: "Cart validation completed" },
      { time: "12:31:35", level: "ERROR", message: "Inventory upstream request timed out" },
      { time: "12:31:28", level: "INFO", message: "Checkout session created" },
      { time: "12:31:21", level: "INFO", message: "Payment method validated" },
    ],
    incidents: [
      {
        id: "checkout-latency",
        severity: "MEDIUM",
        title: "Elevated Checkout Latency",
        serviceId: "checkout-service",
        timeAgo: "11 minutes ago",
        status: "Monitoring",
        analysisTitle: "Elevated Checkout Latency",
      },
    ],
  },
  "auth-service": {
    id: "auth-service",
    name: "Auth Service",
    projectId: "hr-portal",
    analysis: {
      severity: "HIGH",
      title: "Authentication Failure",
      summary:
        "An elevated number of sign-in attempts are failing during token validation.",
      rootCause:
        "Identity provider responses are intermittently timing out during token validation.",
      impact: "Employees may be unable to sign in on their first attempt.",
      recommendations: [
        "Check identity provider availability and response time.",
        "Review token validation errors in the auth service.",
        "Inspect recent authentication configuration changes.",
      ],
      confidence: 91,
      detected: "18m ago",
    },
    logs: [
      { time: "12:31:42", level: "ERROR", message: "Token validation request timed out" },
      { time: "12:31:40", level: "WARN", message: "Identity provider retry scheduled" },
      { time: "12:31:35", level: "INFO", message: "Sign-in request received" },
      { time: "12:31:28", level: "ERROR", message: "Unable to validate session token" },
      { time: "12:31:21", level: "INFO", message: "Auth health check passed" },
    ],
    incidents: [
      {
        id: "auth-validation",
        severity: "HIGH",
        title: "Authentication Failure",
        serviceId: "auth-service",
        timeAgo: "18 minutes ago",
        status: "Investigating",
        analysisTitle: "Authentication Failure",
      },
    ],
  },
  "employee-api": {
    id: "employee-api",
    name: "Employee API",
    projectId: "hr-portal",
    analysis: {
      severity: "LOW",
      title: "Elevated API Response Time",
      summary:
        "A small increase in employee profile response times was detected.",
      rootCause:
        "Profile queries are taking longer while the service handles a routine traffic increase.",
      impact: "Employee profile pages may load slightly more slowly.",
      recommendations: [
        "Monitor profile endpoint latency.",
        "Review database query duration for profile requests.",
        "Reassess if elevated latency persists.",
      ],
      confidence: 82,
      detected: "9m ago",
    },
    logs: [
      { time: "12:31:42", level: "WARN", message: "Profile request completed in 1.8s" },
      { time: "12:31:40", level: "INFO", message: "Employee profile requested" },
      { time: "12:31:35", level: "INFO", message: "Directory sync completed" },
      { time: "12:31:28", level: "INFO", message: "Profile cache refreshed" },
      { time: "12:31:21", level: "INFO", message: "Employee API health check passed" },
    ],
    incidents: [],
  },
  "transfer-api": {
    id: "transfer-api",
    name: "Transfer API",
    projectId: "banking",
    analysis: {
      severity: "HIGH",
      title: "Transfer Processing Delay",
      summary:
        "Several bank transfers are taking longer than expected to be confirmed.",
      rootCause:
        "The transfer processor is waiting on delayed responses from the settlement network.",
      impact: "Transfer confirmations may be delayed for some customers.",
      recommendations: [
        "Check settlement network response times.",
        "Review transfer processor backlog.",
        "Verify pending transfers are being retried safely.",
      ],
      confidence: 90,
      detected: "4m ago",
    },
    logs: [
      { time: "12:31:42", level: "ERROR", message: "Settlement acknowledgement timed out" },
      { time: "12:31:40", level: "WARN", message: "Transfer confirmation delayed" },
      { time: "12:31:35", level: "INFO", message: "Transfer request validated" },
      { time: "12:31:28", level: "ERROR", message: "Settlement network retry 2/3" },
      { time: "12:31:21", level: "INFO", message: "Transfer queued for settlement" },
    ],
    incidents: [
      {
        id: "transfer-settlement",
        severity: "HIGH",
        title: "Transfer Processing Delay",
        serviceId: "transfer-api",
        timeAgo: "4 minutes ago",
        status: "Investigating",
        analysisTitle: "Transfer Processing Delay",
      },
    ],
  },
  "ledger-service": {
    id: "ledger-service",
    name: "Ledger Service",
    projectId: "banking",
    analysis: {
      severity: "MEDIUM",
      title: "Ledger Replication Lag",
      summary:
        "A brief increase in replication lag was observed across ledger replicas.",
      rootCause:
        "One replica is applying ledger updates more slowly than the primary.",
      impact: "Some account balance views may briefly show stale data.",
      recommendations: [
        "Compare replication lag across all ledger replicas.",
        "Inspect replica CPU and storage throughput.",
        "Verify balance reads are routed to the primary when needed.",
      ],
      confidence: 87,
      detected: "13m ago",
    },
    logs: [
      { time: "12:31:42", level: "WARN", message: "Replica lag reached 820ms" },
      { time: "12:31:40", level: "INFO", message: "Ledger entry committed" },
      { time: "12:31:35", level: "INFO", message: "Account balance read" },
      { time: "12:31:28", level: "WARN", message: "Replica catch-up in progress" },
      { time: "12:31:21", level: "INFO", message: "Ledger health check passed" },
    ],
    incidents: [
      {
        id: "ledger-replication",
        severity: "MEDIUM",
        title: "Ledger Replication Lag",
        serviceId: "ledger-service",
        timeAgo: "13 minutes ago",
        status: "Monitoring",
        analysisTitle: "Ledger Replication Lag",
      },
    ],
  },
};

const projectIncidents = {
  ecommerce: [
    serviceData["payment-api"].incidents[0],
    serviceData["payment-api"].incidents[1],
    serviceData["order-service"].incidents[0],
  ],
  "hr-portal": [serviceData["auth-service"].incidents[0]],
  banking: [
    serviceData["transfer-api"].incidents[0],
    serviceData["ledger-service"].incidents[0],
  ],
};

export async function getProjects() {
  return projectData.map((project) => ({
    ...project,
    services: [...project.services],
  }));
}

export async function getLogs(projectId, serviceId) {
  const service = serviceData[serviceId];
  if (!service || service.projectId !== projectId) {
    throw new Error(`No logs found for service "${serviceId}" in project "${projectId}".`);
  }
  return service.logs.map((log) => ({ ...log, service: service.name }));
}

export async function getIncidents(projectId) {
  const incidents = projectIncidents[projectId];
  if (!incidents) {
    throw new Error(`No incidents found for project "${projectId}".`);
  }
  return incidents.map((incident) => ({ ...incident }));
}

export async function analyzeLogs({ project, service, log }) {
  const baseUrl = window.AI_LOG_ASSISTANT_API_URL || "http://127.0.0.1:8002";
  const response = await fetch(`${baseUrl}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, service, log }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || payload.message || `Analysis failed (${response.status}).`;
    throw new Error(message);
  }
  return payload;
}

export async function chatAssistant({ project, service, log, question, history, analysis }) {
  const baseUrl = window.AI_LOG_ASSISTANT_API_URL || "http://127.0.0.1:8002";
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, service, log, question, history, analysis }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || payload.message || `Chat request failed (${response.status}).`;
    throw new Error(message);
  }
  return payload;
}

export function getService(projectId, serviceId) {
  const service = serviceData[serviceId];
  if (!service || service.projectId !== projectId) {
    throw new Error(`Service "${serviceId}" does not belong to project "${projectId}".`);
  }
  return { ...service, analysis: { ...service.analysis } };
}

export function getServiceNames(projectId) {
  const project = projectData.find((item) => item.id === projectId);
  if (!project) {
    throw new Error(`No services found for project "${projectId}".`);
  }
  return project.services.map((serviceId) => {
    const service = serviceData[serviceId];
    return { id: service.id, name: service.name };
  });
}

export function getProjectStats(projectId) {
  const project = projectData.find((item) => item.id === projectId);
  if (!project) {
    throw new Error(`No statistics found for project "${projectId}".`);
  }
  return {
    totalLogs: project.totalLogs,
    errors: project.errors,
    warnings: project.warnings,
    incidents: project.incidents,
  };
}
