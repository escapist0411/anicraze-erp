export const kpis = [
  { label: "Today's sales", value: '₹1,84,260', change: '+12.6%', trend: [32, 48, 40, 58, 51, 72, 68], tone: 'indigo', icon: 'sales' },
  { label: 'Monthly revenue', value: '₹24.8L', change: '+18.4%', trend: [42, 47, 54, 51, 67, 70, 82], tone: 'violet', icon: 'revenue' },
  { label: 'Yearly revenue', value: '₹2.87Cr', change: '+22.1%', trend: [31, 38, 45, 44, 61, 66, 78], tone: 'sky', icon: 'yearly' },
  { label: 'Net profit', value: '₹6.42L', change: '+9.8%', trend: [39, 45, 42, 55, 50, 62, 65], tone: 'emerald', icon: 'profit' },
  { label: 'Inventory value', value: '₹38.6L', change: '+4.2%', trend: [49, 48, 54, 53, 56, 59, 61], tone: 'amber', icon: 'inventory' },
  { label: 'Orders today', value: '126', change: '+14.7%', trend: [22, 28, 24, 35, 31, 45, 48], tone: 'rose', icon: 'orders' },
  { label: 'Customers today', value: '98', change: '+8.3%', trend: [18, 22, 21, 29, 27, 34, 38], tone: 'cyan', icon: 'customers' },
  { label: 'Pending orders', value: '17', change: '-6.1%', trend: [48, 44, 46, 39, 36, 31, 28], tone: 'orange', icon: 'pending' },
] as const;

export const chartData = {
  Daily: [{ label: '9 AM', revenue: 24, profit: 8, orders: 12 }, { label: '11 AM', revenue: 42, profit: 15, orders: 24 }, { label: '1 PM', revenue: 56, profit: 21, orders: 39 }, { label: '3 PM', revenue: 48, profit: 17, orders: 32 }, { label: '5 PM', revenue: 72, profit: 28, orders: 48 }, { label: '7 PM', revenue: 91, profit: 36, orders: 62 }, { label: '9 PM', revenue: 64, profit: 24, orders: 45 }],
  Weekly: [{ label: 'Mon', revenue: 128, profit: 42, orders: 88 }, { label: 'Tue', revenue: 146, profit: 50, orders: 94 }, { label: 'Wed', revenue: 139, profit: 45, orders: 91 }, { label: 'Thu', revenue: 172, profit: 61, orders: 112 }, { label: 'Fri', revenue: 188, profit: 68, orders: 124 }, { label: 'Sat', revenue: 214, profit: 77, orders: 142 }, { label: 'Sun', revenue: 196, profit: 70, orders: 131 }],
  Monthly: [{ label: 'Jan', revenue: 460, profit: 155, orders: 810 }, { label: 'Feb', revenue: 510, profit: 174, orders: 900 }, { label: 'Mar', revenue: 485, profit: 162, orders: 850 }, { label: 'Apr', revenue: 560, profit: 193, orders: 970 }, { label: 'May', revenue: 610, profit: 215, orders: 1050 }, { label: 'Jun', revenue: 580, profit: 202, orders: 1010 }, { label: 'Jul', revenue: 690, profit: 246, orders: 1180 }],
  Yearly: [{ label: '2020', revenue: 32, profit: 11, orders: 65 }, { label: '2021', revenue: 48, profit: 16, orders: 89 }, { label: '2022', revenue: 64, profit: 23, orders: 118 }, { label: '2023', revenue: 91, profit: 32, orders: 152 }, { label: '2024', revenue: 118, profit: 43, orders: 195 }, { label: '2025', revenue: 156, profit: 57, orders: 245 }, { label: '2026', revenue: 187, profit: 69, orders: 296 }],
};

export const stores = [
  { name: 'Phoenix Mall', city: 'Lower Parel, Mumbai', initials: 'PM', revenue: '₹6.82L', profit: '₹1.86L', customers: 462, orders: 318, performance: 94, color: 'bg-violet-500' },
  { name: 'Seawoods', city: 'Navi Mumbai', initials: 'SW', revenue: '₹5.94L', profit: '₹1.54L', customers: 391, orders: 286, performance: 86, color: 'bg-sky-500' },
  { name: 'Palladium', city: 'Lower Parel, Mumbai', initials: 'PA', revenue: '₹5.76L', profit: '₹1.48L', customers: 374, orders: 259, performance: 82, color: 'bg-amber-500' },
  { name: 'Viviana', city: 'Thane West', initials: 'VI', revenue: '₹4.89L', profit: '₹1.27L', customers: 328, orders: 225, performance: 74, color: 'bg-emerald-500' },
  { name: 'Nexus', city: 'Seawoods, Navi Mumbai', initials: 'NX', revenue: '₹3.62L', profit: '₹0.91L', customers: 244, orders: 181, performance: 61, color: 'bg-rose-500' },
];

export const products = [
  { name: 'Tanjiro Kamado — Hinokami', category: 'Action Figures', units: 84, revenue: '₹2,09,160', stock: 32, status: 'Healthy', hue: 'from-emerald-400 to-teal-600' },
  { name: 'Gojo Satoru — Hollow Purple', category: 'Collectibles', units: 68, revenue: '₹1,76,120', stock: 14, status: 'Low stock', hue: 'from-violet-400 to-indigo-600' },
  { name: 'Luffy Gear 5 — Nika', category: 'Action Figures', units: 57, revenue: '₹1,53,900', stock: 26, status: 'Healthy', hue: 'from-orange-400 to-rose-600' },
  { name: 'Chainsaw Man — Pochita', category: 'Plush & Gifts', units: 49, revenue: '₹97,510', stock: 8, status: 'Low stock', hue: 'from-amber-300 to-orange-600' },
  { name: 'Itachi Uchiha — ANBU', category: 'Statues', units: 41, revenue: '₹1,31,610', stock: 0, status: 'Out of stock', hue: 'from-slate-500 to-zinc-800' },
];

export const orders = [
  { invoice: '#AN-20481', customer: 'Aarav Mehta', store: 'Phoenix Mall', amount: '₹7,450', payment: 'UPI', status: 'Paid', time: '2 min ago' },
  { invoice: '#AN-20480', customer: 'Nisha Kapoor', store: 'Seawoods', amount: '₹12,800', payment: 'Card', status: 'Paid', time: '8 min ago' },
  { invoice: '#AN-20479', customer: 'Kunal Shah', store: 'Palladium', amount: '₹4,290', payment: 'Cash', status: 'Processing', time: '15 min ago' },
  { invoice: '#AN-20478', customer: 'Riya Iyer', store: 'Viviana', amount: '₹18,640', payment: 'Card', status: 'Paid', time: '22 min ago' },
  { invoice: '#AN-20477', customer: 'Dev Malhotra', store: 'Nexus', amount: '₹6,990', payment: 'UPI', status: 'Pending', time: '29 min ago' },
];

export const activities = [
  { title: 'New product added', detail: 'Gojo Satoru — Hollow Purple was added to the catalog.', time: '12 min ago', tone: 'bg-violet-500' },
  { title: 'Stock level updated', detail: 'Phoenix Mall received 36 units across 4 SKUs.', time: '34 min ago', tone: 'bg-sky-500' },
  { title: 'Invoice generated', detail: 'Invoice #AN-20481 was created for Aarav Mehta.', time: '42 min ago', tone: 'bg-emerald-500' },
  { title: 'Employee sign-in', detail: 'Meera Joshi signed in at the Seawoods store.', time: '1 hr ago', tone: 'bg-amber-500' },
  { title: 'Store updated', detail: 'Palladium store hours were updated for the weekend.', time: '2 hr ago', tone: 'bg-rose-500' },
];
