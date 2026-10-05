/**
 * ==============================================================================
 * THINK STUDIO — GOOGLE APPS SCRIPT (Code.gs)
 * Automated Executive Dashboard & Real-Time Sync Engine
 * ==============================================================================
 * 
 * Features:
 * 1. Left Side: Customer & Member Master Directory (Columns A to M)
 * 2. Right Side: Executive KPI Cards, Monthly Payments Table & Package Breakdown (Columns O to T)
 * 3. Smart Row Updating: Updates existing customer records in-place (no duplicate rows)
 * 4. Recent Verified Payments Ledger automatically updated
 * 5. One-click setup: Run setupThinkStudioDashboard() or click from the custom menu
 * ==============================================================================
 */

const SHEET_NAME = "Think Studio Dashboard";

/**
 * Custom Menu inside Google Sheets
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('✨ Think Studio')
    .addItem('🌟 Load Real Data (Kavindya, Menuka & Janith)', 'loadRealData')
    .addItem('📌 Update Menuka Today Session (3.5h • Rs. 4,500 Unpaid)', 'updateMenukaTodaySession')
    .addItem('🎨 Setup & Format Dashboard', 'setupThinkStudioDashboard')
    .addSeparator()
    .addItem('🔄 Recalculate Financials', 'recalculateFinancials')
    .addItem('🧪 Add Sample Data (නියැදි දත්ත)', 'addSampleData')
    .addItem('🧹 Clear Data (දත්ත ඉවත් කරන්න)', 'clearSampleData')
    .addToUi();
}

/**
 * Handle incoming POST requests from Think Studio Server / Client Webhook
 */
function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(15000); // Wait up to 15s to prevent concurrent write collisions
    
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = setupThinkStudioDashboard();
    }
    
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({ result: "error", message: "No payload received" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    const data = JSON.parse(e.postData.contents);
    
    // 1. If payment verification information is included, record into the Payments Ledger
    if (data.payment || data.action === "payment_verified") {
      recordPaymentLog(sheet, data);
    }
    
    // 2. Update or insert the Customer Record in the main directory
    const updateResult = upsertCustomerRow(sheet, data);
    
    return ContentService.createTextOutput(JSON.stringify({
      result: "success",
      action: updateResult.action,
      row: updateResult.row,
      client: data.name || data.email,
      timestamp: new Date().toISOString()
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      result: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

/**
 * Handle GET requests (Healthcheck)
 */
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "online",
    system: "Think Studio Live Sync Webhook",
    version: "2.0",
    sheetName: SHEET_NAME,
    timestamp: new Date().toISOString()
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Setup and Format the Entire Executive Dashboard
 */
function setupThinkStudioDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME, 0);
  }
  
  // Set tab color
  sheet.setTabColor("#D4AF37");
  
  // CRITICAL FIX: Unfreeze all columns and rows before clearing and merging
  sheet.setFrozenColumns(0);
  sheet.setFrozenRows(0);
  sheet.clear();

  // Ensure sufficient dimensions (at least 22 columns A to V, and at least 100 rows)
  if (sheet.getMaxColumns() < 22) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), 22 - sheet.getMaxColumns());
  }
  if (sheet.getMaxRows() < 100) {
    sheet.insertRowsAfter(sheet.getMaxRows(), 100 - sheet.getMaxRows());
  }

  // -------------------------------------------------------------
  // 1. MAIN HEADER BANNER (Row 1 & 2)
  // -------------------------------------------------------------
  sheet.getRange("A1:T1").merge();
  const banner = sheet.getRange("A1");
  banner.setValue("✨ THINK STUDIO — EXECUTIVE CLIENT & FINANCIAL DASHBOARD");
  banner.setBackground("#0F1117");
  banner.setFontColor("#D4AF37");
  banner.setFontSize(14);
  banner.setFontWeight("bold");
  banner.setHorizontalAlignment("center");
  banner.setVerticalAlignment("middle");
  sheet.setRowHeight(1, 40);

  sheet.getRange("A2:T2").merge();
  const subBanner = sheet.getRange("A2");
  subBanner.setValue("● REAL-TIME LIVE SYNC CONNECTED   |   PEOPLE'S BANK A/C: 245200290056879 (E.M.S.S. FONSEKA)   |   AUTOMATED FINANCIAL LEDGER");
  subBanner.setBackground("#181A22");
  subBanner.setFontColor("#94A3B8");
  subBanner.setFontSize(9);
  subBanner.setFontFamily("Consolas");
  subBanner.setHorizontalAlignment("center");
  subBanner.setVerticalAlignment("middle");
  sheet.setRowHeight(2, 22);

  // -------------------------------------------------------------
  // 2. MAIN TABLE HEADERS (Columns A to M, Row 3)
  // -------------------------------------------------------------
  const mainHeaders = [
    "Sync Timestamp", "Client ID", "Customer Name", "Email Address", "Phone",
    "Package Name", "Package Fee", "Amount Paid", "Balance Due",
    "Total Hrs", "Used Hrs", "Remaining Hrs", "Status"
  ];
  const mainHRange = sheet.getRange(3, 1, 1, mainHeaders.length);
  mainHRange.setValues([mainHeaders]);
  mainHRange.setBackground("#1E2028");
  mainHRange.setFontColor("#D4AF37");
  mainHRange.setFontWeight("bold");
  mainHRange.setFontSize(10);
  mainHRange.setHorizontalAlignment("center");
  mainHRange.setVerticalAlignment("middle");
  sheet.setRowHeight(3, 30);

  // Column Widths for Main Table
  sheet.setColumnWidth(1, 140); // Timestamp
  sheet.setColumnWidth(2, 90);  // Client ID
  sheet.setColumnWidth(3, 160); // Customer Name
  sheet.setColumnWidth(4, 180); // Email
  sheet.setColumnWidth(5, 120); // Phone
  sheet.setColumnWidth(6, 140); // Package
  sheet.setColumnWidth(7, 110); // Fee
  sheet.setColumnWidth(8, 110); // Paid
  sheet.setColumnWidth(9, 110); // Balance
  sheet.setColumnWidth(10, 80); // Total Hrs
  sheet.setColumnWidth(11, 80); // Used Hrs
  sheet.setColumnWidth(12, 100); // Remaining Hrs
  sheet.setColumnWidth(13, 90); // Status

  // Spacer Column N
  sheet.setColumnWidth(14, 25);
  sheet.getRange("N1:N100").setBackground("#0B0C10");

  // -------------------------------------------------------------
  // 3. RIGHT SIDE: EXECUTIVE KPI CARDS (Columns O to T, Rows 3 to 5)
  // -------------------------------------------------------------
  // Card 1: Total Revenue (Cols O-P)
  sheet.getRange("O3:P3").merge().setValue("💰 TOTAL STUDIO REVENUE")
    .setBackground("#181A22").setFontColor("#94A3B8").setFontSize(9).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.getRange("O4:P5").merge().setFormula("=SUM(G4:G100)")
    .setBackground("#12141F").setFontColor("#FFFFFF").setFontSize(16).setFontWeight("bold").setNumberFormat("[$Rs. ]#,##0.00").setHorizontalAlignment("center").setVerticalAlignment("middle");

  // Card 2: Total Collected (Cols Q-R)
  sheet.getRange("Q3:R3").merge().setValue("💳 TOTAL CASH COLLECTED")
    .setBackground("#181A22").setFontColor("#10B981").setFontSize(9).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.getRange("Q4:R5").merge().setFormula("=SUM(H4:H100)")
    .setBackground("#12141F").setFontColor("#10B981").setFontSize(16).setFontWeight("bold").setNumberFormat("[$Rs. ]#,##0.00").setHorizontalAlignment("center").setVerticalAlignment("middle");

  // Card 3: Outstanding Due (Cols S-T)
  sheet.getRange("S3:T3").merge().setValue("⏳ OUTSTANDING BALANCE DUE")
    .setBackground("#181A22").setFontColor("#EF4444").setFontSize(9).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.getRange("S4:T5").merge().setFormula("=SUM(I4:I100)")
    .setBackground("#12141F").setFontColor("#EF4444").setFontSize(16).setFontWeight("bold").setNumberFormat("[$Rs. ]#,##0.00").setHorizontalAlignment("center").setVerticalAlignment("middle");

  // -------------------------------------------------------------
  // 4. RIGHT SIDE: MONTHLY PAYMENTS TABLE (Rows 7 to 15)
  // -------------------------------------------------------------
  sheet.getRange("O7:T7").merge().setValue("📅 MONTHLY PAYMENTS & REVENUE BREAKDOWN (මාසික ගෙවීම් සාරාංශය)")
    .setBackground("#1E2028").setFontColor("#D4AF37").setFontSize(10).setFontWeight("bold").setHorizontalAlignment("left");
  sheet.setRowHeight(7, 26);

  const monthlyHeaders = ["Month (මාසය)", "Active Clients", "Total Billed (Rs.)", "Collected (Rs.)", "Pending Due (Rs.)", "Collection %"];
  sheet.getRange("O8:T8").setValues([monthlyHeaders])
    .setBackground("#181A22").setFontColor("#E2E8F0").setFontSize(9).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.setRowHeight(8, 24);

  const months = [
    ["September 2026",
     '=COUNTIFS(A4:A100,">="&DATE(2026,9,1),A4:A100,"<"&DATE(2026,10,1),M4:M100,"<>")',
     '=SUMIFS(G4:G100,A4:A100,">="&DATE(2026,9,1),A4:A100,"<"&DATE(2026,10,1))',
     '=SUMIFS(H4:H100,A4:A100,">="&DATE(2026,9,1),A4:A100,"<"&DATE(2026,10,1))',
     '=SUMIFS(I4:I100,A4:A100,">="&DATE(2026,9,1),A4:A100,"<"&DATE(2026,10,1))',
     '=IF(Q9>0,R9/Q9,0)'],
    ["October 2026",
     '=COUNTIFS(A4:A100,">="&DATE(2026,10,1),A4:A100,"<"&DATE(2026,11,1),M4:M100,"<>")',
     '=SUMIFS(G4:G100,A4:A100,">="&DATE(2026,10,1),A4:A100,"<"&DATE(2026,11,1))',
     '=SUMIFS(H4:H100,A4:A100,">="&DATE(2026,10,1),A4:A100,"<"&DATE(2026,11,1))',
     '=SUMIFS(I4:I100,A4:A100,">="&DATE(2026,10,1),A4:A100,"<"&DATE(2026,11,1))',
     '=IF(Q10>0,R10/Q10,0)'],
    ["November 2026",
     '=COUNTIFS(A4:A100,">="&DATE(2026,11,1),A4:A100,"<"&DATE(2026,12,1),M4:M100,"<>")',
     '=SUMIFS(G4:G100,A4:A100,">="&DATE(2026,11,1),A4:A100,"<"&DATE(2026,12,1))',
     '=SUMIFS(H4:H100,A4:A100,">="&DATE(2026,11,1),A4:A100,"<"&DATE(2026,12,1))',
     '=SUMIFS(I4:I100,A4:A100,">="&DATE(2026,11,1),A4:A100,"<"&DATE(2026,12,1))',
     '=IF(Q11>0,R11/Q11,0)'],
    ["December 2026",
     '=COUNTIFS(A4:A100,">="&DATE(2026,12,1),A4:A100,"<"&DATE(2027,1,1),M4:M100,"<>")',
     '=SUMIFS(G4:G100,A4:A100,">="&DATE(2026,12,1),A4:A100,"<"&DATE(2027,1,1))',
     '=SUMIFS(H4:H100,A4:A100,">="&DATE(2026,12,1),A4:A100,"<"&DATE(2027,1,1))',
     '=SUMIFS(I4:I100,A4:A100,">="&DATE(2026,12,1),A4:A100,"<"&DATE(2027,1,1))',
     '=IF(Q12>0,R12/Q12,0)'],
    ["January 2027",
     '=COUNTIFS(A4:A100,">="&DATE(2027,1,1),A4:A100,"<"&DATE(2027,2,1),M4:M100,"<>")',
     '=SUMIFS(G4:G100,A4:A100,">="&DATE(2027,1,1),A4:A100,"<"&DATE(2027,2,1))',
     '=SUMIFS(H4:H100,A4:A100,">="&DATE(2027,1,1),A4:A100,"<"&DATE(2027,2,1))',
     '=SUMIFS(I4:I100,A4:A100,">="&DATE(2027,1,1),A4:A100,"<"&DATE(2027,2,1))',
     '=IF(Q13>0,R13/Q13,0)'],
    ["February 2027",
     '=COUNTIFS(A4:A100,">="&DATE(2027,2,1),A4:A100,"<"&DATE(2027,3,1),M4:M100,"<>")',
     '=SUMIFS(G4:G100,A4:A100,">="&DATE(2027,2,1),A4:A100,"<"&DATE(2027,3,1))',
     '=SUMIFS(H4:H100,A4:A100,">="&DATE(2027,2,1),A4:A100,"<"&DATE(2027,3,1))',
     '=SUMIFS(I4:I100,A4:A100,">="&DATE(2027,2,1),A4:A100,"<"&DATE(2027,3,1))',
     '=IF(Q14>0,R14/Q14,0)']
  ];
  sheet.getRange("O9:T14").setValues(months).setFontSize(9).setBackground("#0F1117").setFontColor("#F1F5F9");
  
  // Total Row for Monthly Table
  const totalMonthlyRow = ["TOTAL / YEAR-TO-DATE", '=SUM(P9:P14)', '=SUM(Q9:Q14)', '=SUM(R9:R14)', '=SUM(S9:S14)', '=IF(Q15>0,R15/Q15,0)'];
  sheet.getRange("O15:T15").setValues([totalMonthlyRow])
    .setBackground("#1E2028").setFontColor("#D4AF37").setFontWeight("bold").setFontSize(9);

  sheet.getRange("Q9:S15").setNumberFormat("[$Rs. ]#,##0.00");
  sheet.getRange("T9:T15").setNumberFormat("0.0%");
  sheet.getRange("P9:P15").setHorizontalAlignment("center");

  // -------------------------------------------------------------
  // 5. RIGHT SIDE: RECENT VERIFIED PAYMENTS LEDGER (Rows 17 to 25)
  // -------------------------------------------------------------
  sheet.getRange("O17:T17").merge().setValue("🏦 RECENT VERIFIED BANK DEPOSITS (මෑතකදී ලැබුණු ගෙවීම්)")
    .setBackground("#1E2028").setFontColor("#10B981").setFontSize(10).setFontWeight("bold").setHorizontalAlignment("left");
  sheet.setRowHeight(17, 26);

  const paymentHeaders = ["Deposit Date", "Customer Name", "Amount (Rs.)", "Bank Ref #", "Payment Method", "Status"];
  sheet.getRange("O18:T18").setValues([paymentHeaders])
    .setBackground("#181A22").setFontColor("#E2E8F0").setFontSize(9).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.setRowHeight(18, 24);

  // Default empty rows for payments (Rows 19-25)
  sheet.getRange("O19:T25").setBackground("#0F1117").setFontColor("#F1F5F9").setFontSize(9).clearContent();
  sheet.getRange("Q19:Q25").setNumberFormat("[$Rs. ]#,##0.00");

  // Seed initial verified payment
  sheet.getRange("O19:T19").setValues([
    ["2026-09-20", "Dr. Rajesh Sharma", 8000, "REF-PEOPLES-9921", "People's Bank Godakawela", "Verified"]
  ]);

  // -------------------------------------------------------------
  // 6. RIGHT SIDE: PACKAGE DISTRIBUTION & UTILIZATION (Rows 27 to 32)
  // -------------------------------------------------------------
  sheet.getRange("O27:T27").merge().setValue("📦 PACKAGE DISTRIBUTION & HOURS UTILIZATION (පැකේජ විස්තරය)")
    .setBackground("#1E2028").setFontColor("#60A5FA").setFontSize(10).setFontWeight("bold").setHorizontalAlignment("left");
  sheet.setRowHeight(27, 26);

  const packageHeaders = ["Package Name", "Base Price", "Active Clients", "Total Hours", "Used Hours", "Remaining Hours"];
  sheet.getRange("O28:T28").setValues([packageHeaders])
    .setBackground("#181A22").setFontColor("#E2E8F0").setFontSize(9).setFontWeight("bold").setHorizontalAlignment("center");
  sheet.setRowHeight(28, 24);

  const packagesData = [
    ["Single Module (2 Hours)", 1800, '=COUNTIF(F4:F, "*Single*")', '=SUMIF(F4:F, "*Single*", J4:J)', '=SUMIF(F4:F, "*Single*", K4:K)', '=SUMIF(F4:F, "*Single*", L4:L)'],
    ["Pro Lecturer (10 Hours)", 7500, '=COUNTIF(F4:F, "*Pro*") + COUNTIF(F4:F, "*Flex*")', '=SUMIF(F4:F, "*Pro*", J4:J) + SUMIF(F4:F, "*Flex*", J4:J)', '=SUMIF(F4:F, "*Pro*", K4:K) + SUMIF(F4:F, "*Flex*", K4:K)', '=SUMIF(F4:F, "*Pro*", L4:L) + SUMIF(F4:F, "*Flex*", L4:L)'],
    ["Monthly Package (20 Hours)", 12000, '=COUNTIF(F4:F, "*Monthly*") + COUNTIF(F4:F, "*Master*")', '=SUMIF(F4:F, "*Monthly*", J4:J) + SUMIF(F4:F, "*Master*", J4:J)', '=SUMIF(F4:F, "*Monthly*", K4:K) + SUMIF(F4:F, "*Master*", K4:K)', '=SUMIF(F4:F, "*Monthly*", L4:L) + SUMIF(F4:F, "*Master*", L4:L)'],
    ["Unlimited Prime (40 Hours)", 20000, '=COUNTIF(F4:F, "*Unlimited*") + COUNTIF(F4:F, "*Prime*")', '=SUMIF(F4:F, "*Unlimited*", J4:J) + SUMIF(F4:F, "*Prime*", J4:J)', '=SUMIF(F4:F, "*Unlimited*", K4:K) + SUMIF(F4:F, "*Prime*", K4:K)', '=SUMIF(F4:F, "*Unlimited*", L4:L) + SUMIF(F4:F, "*Prime*", L4:L)'],
    ["TOTAL STUDIO USAGE", '=SUM(P29:P32)', '=SUM(Q29:Q32)', '=SUM(R29:R32)', '=SUM(S29:S32)', '=SUM(T29:T32)']
  ];
  sheet.getRange("O29:T33").setValues(packagesData).setFontSize(9).setBackground("#0F1117").setFontColor("#F1F5F9");
  sheet.getRange("O33:T33").setBackground("#1E2028").setFontColor("#D4AF37").setFontWeight("bold");
  sheet.getRange("P29:P33").setNumberFormat("[$Rs. ]#,##0.00");
  sheet.getRange("Q29:T33").setHorizontalAlignment("center");

  // Column Widths for Right Side Dashboard
  sheet.setColumnWidth(15, 140); // Month / Date / Package
  sheet.setColumnWidth(16, 110); // Active / Cust / Price
  sheet.setColumnWidth(17, 120); // Billed / Amount / Active
  sheet.setColumnWidth(18, 120); // Collected / Ref / Total Hrs
  sheet.setColumnWidth(19, 120); // Pending / Method / Used Hrs
  sheet.setColumnWidth(20, 110); // Rate % / Status / Rem Hrs

  // Apply Borders to Tables
  sheet.getRange("O3:T5").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange("O7:T15").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange("O17:T25").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange("O27:T32").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);

  // Main table default number formatting
  sheet.getRange("B4:B100").setNumberFormat("@"); // Client ID as Plain Text
  sheet.getRange("D4:D100").setNumberFormat("@"); // Email as Plain Text
  sheet.getRange("E4:E100").setNumberFormat("@"); // Phone as Plain Text (prevents +94 formula #ERROR!)
  sheet.getRange("G4:I100").setNumberFormat("[$Rs. ]#,##0.00");
  sheet.getRange("J4:L100").setNumberFormat("#0");

  // Conditional Formatting Rules
  applyConditionalRules(sheet);

  // Freeze top 3 header rows only (unfreeze columns so merging and scrolling work cleanly)
  sheet.setFrozenRows(3);
  sheet.setFrozenColumns(0);

  return sheet;
}

/**
 * Apply Conditional Formatting for Status, Balances & Hours
 */
function applyConditionalRules(sheet) {
  const rules = [];

  // 1. Status Column M: "Active" -> Green
  const statusRange = sheet.getRange("M4:M100");
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("Active")
    .setBackground("#064E3B").setFontColor("#34D399")
    .setRanges([statusRange]).build());

  // 2. Balance Due Column I: > 0 -> Amber/Red alert
  const balRange = sheet.getRange("I4:I100");
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThan(0)
    .setBackground("#451A03").setFontColor("#FBBF24")
    .setRanges([balRange]).build());

  // 3. Balance Due Column I: == 0 -> Green (Fully paid)
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenNumberEqualTo(0)
    .setBackground("#064E3B").setFontColor("#6EE7B7")
    .setRanges([balRange]).build());

  // 4. Remaining Hours Column L: <= 3 -> Low balance alert
  const remRange = sheet.getRange("L4:L100");
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenNumberLessThanOrEqualTo(3)
    .setBackground("#7F1D1D").setFontColor("#FCA5A5")
    .setRanges([remRange]).build());

  sheet.setConditionalFormatRules(rules);
}

/**
 * Smart Upsert: Find existing user row by Email or ID and update in-place;
 * otherwise append a new row at the bottom of the Customer Directory.
 */
function upsertCustomerRow(sheet, data) {
  const email = (data.email || "").toString().trim().toLowerCase();
  const userId = (data.id || "").toString().trim();
  
  const timestamp = data.timestamp || Utilities.formatDate(new Date(), "Asia/Colombo", "yyyy-MM-dd HH:mm");
  const name = data.name || "Customer";
  let phone = (data.phone || "").toString().trim();
  if (phone && !phone.startsWith("'")) {
    phone = "'" + phone;
  }
  const packageName = data.packageName || "Monthly Package";
  const packagePrice = Number(data.packagePrice) || 12000;
  const balanceDue = Number(data.balanceDue !== undefined ? data.balanceDue : 0);
  const paidAmount = Number(data.paidAmount !== undefined ? data.paidAmount : (packagePrice - balanceDue));
  const totalHours = Number(data.totalHours) || 20;
  const remainingHours = Number(data.remainingHours !== undefined ? data.remainingHours : 12);
  const usedHours = Number(data.usedHours !== undefined ? data.usedHours : Math.max(0, totalHours - remainingHours));
  const status = data.status || (remainingHours > 0 ? "Active" : "Expired");

  const rowValues = [
    timestamp,
    userId,
    name,
    email,
    phone,
    packageName,
    packagePrice,
    paidAmount,
    balanceDue,
    totalHours,
    usedHours,
    remainingHours,
    status
  ];

  // Scan Column D (Email) and Column B (ID) to find existing row
  const lastRow = Math.max(4, sheet.getLastRow());
  const existingEmails = sheet.getRange(4, 4, lastRow - 3, 1).getValues();
  const existingIds = sheet.getRange(4, 2, lastRow - 3, 1).getValues();

  let targetRow = -1;
  for (let i = 0; i < existingEmails.length; i++) {
    const curEmail = existingEmails[i][0].toString().trim().toLowerCase();
    const curId = existingIds[i][0].toString().trim();
    if ((email && curEmail === email) || (userId && curId === userId)) {
      targetRow = i + 4; // 1-indexed, starting at row 4
      break;
    }
  }

  if (targetRow !== -1) {
    // UPDATE existing row in place
    sheet.getRange(targetRow, 1, 1, rowValues.length).setValues([rowValues]);
    sheet.getRange(targetRow, 1, 1, rowValues.length).setBackground("#12141F").setFontColor("#F8FAFC").setFontSize(9);
    sheet.getRange(targetRow, 1, 1, rowValues.length).setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);
    return { action: "updated", row: targetRow };
  } else {
    // APPEND new customer row dynamically across all rows (No 100-row limit)
    const lastRow = Math.max(4, sheet.getLastRow());
    let emptyRow = -1;

    // Scan column C (Customer Name) from row 4 to lastRow
    const numRowsToCheck = Math.max(1, lastRow - 3);
    const namesCol = sheet.getRange(4, 3, numRowsToCheck, 1).getValues();
    for (let k = 0; k < namesCol.length; k++) {
      if (!namesCol[k][0] || namesCol[k][0].toString().trim() === "") {
        emptyRow = k + 4;
        break;
      }
    }

    // If all existing rows are full, append at lastRow + 1 (never overwrite row 4!)
    if (emptyRow === -1) {
      emptyRow = lastRow + 1;
    }

    // If emptyRow exceeds sheet capacity, automatically add rows
    if (emptyRow > sheet.getMaxRows()) {
      sheet.insertRowsAfter(sheet.getMaxRows(), 50);
    }

    sheet.getRange(emptyRow, 1, 1, rowValues.length).setValues([rowValues]);
    sheet.getRange(emptyRow, 1, 1, rowValues.length).setBackground("#12141F").setFontColor("#F8FAFC").setFontSize(9);
    sheet.getRange(emptyRow, 1, 1, rowValues.length).setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);
    return { action: "inserted", row: emptyRow };
  }
}

/**
 * Log Verified Payment into Recent Bank Deposits Table (Rows 19 to 25)
 */
function recordPaymentLog(sheet, data) {
  const p = data.payment || {};
  const payDate = p.date || Utilities.formatDate(new Date(), "Asia/Colombo", "yyyy-MM-dd");
  const custName = data.name || p.userName || "Studio Client";
  const amount = Number(p.amount || data.paidAmount || 0);
  const ref = p.ref || "REF-" + Date.now().toString().slice(-6);
  const method = p.method || "People's Bank Godakawela";
  const status = p.status || "Verified";

  if (amount <= 0) return;

  // Shift existing payment rows down (Rows 19-24 down to 20-25)
  const existingRows = sheet.getRange("O19:T24").getValues();
  sheet.getRange("O20:T25").setValues(existingRows);

  // Insert new payment at top of table (Row 19)
  sheet.getRange("O19:T19").setValues([[payDate, custName, amount, ref, method, status]])
    .setBackground("#12141F").setFontColor("#34D399").setFontSize(9).setFontWeight("bold");
}

/**
 * Force recalculation of formulas and monthly summaries
 */
function recalculateFinancials() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) return;

  const data = sheet.getRange("A4:M100").getValues();
  const monthlyStats = {};

  for (let r = 0; r < data.length; r++) {
    const rawDate = data[r][0];
    const clientName = data[r][2];
    if (!clientName || clientName.toString().trim() === "") continue;

    let d = null;
    if (rawDate instanceof Date) {
      d = rawDate;
    } else if (rawDate) {
      d = new Date(rawDate.toString().replace(/-/g, "/"));
    }
    
    if (d && !isNaN(d.getTime())) {
      const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
      const monthKey = monthNames[d.getMonth()] + " " + d.getFullYear();
      if (!monthlyStats[monthKey]) {
        monthlyStats[monthKey] = { count: 0, billed: 0, paid: 0, balance: 0 };
      }
      monthlyStats[monthKey].count += 1;
      monthlyStats[monthKey].billed += Number(data[r][6]) || 0;
      monthlyStats[monthKey].paid += Number(data[r][7]) || 0;
      monthlyStats[monthKey].balance += Number(data[r][8]) || 0;
    }
  }

  // Check if any month was calculated; if so, populate rows 9 to 14
  const monthRows = sheet.getRange("O9:O14").getValues();
  for (let m = 0; m < monthRows.length; m++) {
    const mName = monthRows[m][0].toString().trim();
    if (monthlyStats[mName]) {
      const stat = monthlyStats[mName];
      const rate = stat.billed > 0 ? (stat.paid / stat.billed) : 0;
      sheet.getRange(9 + m, 16, 1, 5).setValues([[
        stat.count, stat.billed, stat.paid, stat.balance, rate
      ]]);
    }
  }

  SpreadsheetApp.flush();
  SpreadsheetApp.getActiveSpreadsheet().toast("✓ Financial Ledger and Monthly Summaries Recalculated!", "Think Studio", 4);
}

/**
 * Add realistic sample customer and financial data
 */
function addSampleData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME) || setupThinkStudioDashboard();

  // Clear any previous rows so samples occupy Rows 4 to 8 cleanly
  sheet.getRange("A4:M100").clearContent();
  sheet.getRange("A4:M100").setBackground("#12141F");

  // 1. Dr. Rajesh Sharma (Monthly Package, partial balance)
  upsertCustomerRow(sheet, {
    id: "u-1",
    name: "Dr. Rajesh Sharma",
    email: "dr.rajesh@gmail.com",
    phone: "+94 77 123 4567",
    packageName: "Monthly Package",
    packagePrice: 12000,
    paidAmount: 8000,
    balanceDue: 4000,
    totalHours: 20,
    usedHours: 8,
    remainingHours: 12,
    status: "Active",
    timestamp: "2026-09-20 14:30"
  });

  // 2. Mrs. Anoma Jayawardena (10-Hour Flex, Fully Paid)
  upsertCustomerRow(sheet, {
    id: "u-2",
    name: "Mrs. Anoma Jayawardena",
    email: "anoma.j@gmail.com",
    phone: "+94 71 889 2341",
    packageName: "10-Hour Flex Package",
    packagePrice: 7500,
    paidAmount: 7500,
    balanceDue: 0,
    totalHours: 10,
    usedHours: 4,
    remainingHours: 6,
    status: "Active",
    timestamp: "2026-09-22 10:15"
  });

  // 3. Prof. Nimal Perera (Monthly Package, Fully Paid)
  upsertCustomerRow(sheet, {
    id: "u-3",
    name: "Prof. Nimal Perera",
    email: "nimal.p@gmail.com",
    phone: "+94 72 456 7890",
    packageName: "Monthly Package",
    packagePrice: 12000,
    paidAmount: 12000,
    balanceDue: 0,
    totalHours: 20,
    usedHours: 15,
    remainingHours: 5,
    status: "Active",
    timestamp: "2026-09-25 16:00"
  });

  // 4. Mr. Kasun Bandara (Single Masterclass, Expired/0 Hours Left)
  upsertCustomerRow(sheet, {
    id: "u-4",
    name: "Mr. Kasun Bandara",
    email: "kasun.ict@gmail.com",
    phone: "+94 75 334 1122",
    packageName: "Single Masterclass",
    packagePrice: 3500,
    paidAmount: 3500,
    balanceDue: 0,
    totalHours: 3,
    usedHours: 3,
    remainingHours: 0,
    status: "Expired",
    timestamp: "2026-09-27 18:45"
  });

  // 5. Dr. Chamari Wickramasinghe (October 2026 Monthly Package)
  upsertCustomerRow(sheet, {
    id: "u-5",
    name: "Dr. Chamari Wickramasinghe",
    email: "chamari.chem@gmail.com",
    phone: "+94 76 990 4455",
    packageName: "Monthly Package",
    packagePrice: 12000,
    paidAmount: 6000,
    balanceDue: 6000,
    totalHours: 20,
    usedHours: 2,
    remainingHours: 18,
    status: "Active",
    timestamp: "2026-10-01 09:30"
  });

  // Populate Recent Verified Payments Table (Rows 19 to 23)
  const samplePayments = [
    ["2026-10-01", "Dr. Chamari Wickramasinghe", 6000, "PB-9984120", "People's Bank Godakawela", "Verified"],
    ["2026-09-28", "Mrs. Anoma Jayawardena", 7500, "PB-7842109", "People's Bank Godakawela", "Verified"],
    ["2026-09-25", "Prof. Nimal Perera", 12000, "PB-5519802", "People's Bank Godakawela", "Verified"],
    ["2026-09-20", "Dr. Rajesh Sharma", 8000, "PB-3321477", "People's Bank Godakawela", "Verified"],
    ["2026-09-15", "Mr. Kasun Bandara", 3500, "PB-1102934", "People's Bank Godakawela", "Verified"]
  ];
  sheet.getRange("O19:T23").setValues(samplePayments)
    .setBackground("#12141F").setFontColor("#F8FAFC").setFontSize(9);
  sheet.getRange("Q19:Q23").setNumberFormat("[$Rs. ]#,##0.00").setFontColor("#34D399").setFontWeight("bold");

  recalculateFinancials();
  SpreadsheetApp.getActiveSpreadsheet().toast("✓ Realistic sample customers & financial data loaded!", "Think Studio", 5);
}

/**
 * Clear only sample data rows while strictly preserving all headers, formatting,
 * formulas, side dashboard tables, and KPI cards!
 */
function clearSampleData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) return;

  // Clear customer rows (Columns A to M, Row 4 to Row 100)
  sheet.getRange("A4:M100").clearContent();
  sheet.getRange("A4:M100").setBackground("#12141F").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);

  // Clear recent payments table (Columns O to T, Row 19 to Row 25)
  sheet.getRange("O19:T25").clearContent();
  sheet.getRange("O19:T25").setBackground("#0F1117").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);

  recalculateFinancials();
  SpreadsheetApp.getActiveSpreadsheet().toast("✓ Sample data removed cleanly. Ready for real customers!", "Think Studio", 5);
}

/**
 * Load REAL Customer & Financial Records (Kavindya Kodithuwakku & Menuka Wijebandara)
 */
function loadRealData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME) || setupThinkStudioDashboard();

  // Clear any existing sample/test rows first (wipes rows 4-100 and side payments table)
  sheet.getRange("A4:M100").clearContent();
  sheet.getRange("A4:M100").setBackground("#12141F").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange("O19:T25").clearContent();
  sheet.getRange("O19:T25").setBackground("#0F1117").setBorder(true, true, true, true, true, true, "#334155", SpreadsheetApp.BorderStyle.SOLID);

  // 1. Kavindya Kodithuwakku (Rs. 15,000 paid on 09/26/2026, 3h session 6PM-9PM for Oct 3 & Oct 4, 0 balance)
  upsertCustomerRow(sheet, {
    id: "u-kavindya",
    name: "Kavindya Kodithuwakku",
    email: "kavindya.kodithuwakku@gmail.com",
    phone: "0702663137",
    packageName: "Master Session (3h • 6PM-9PM • Oct 3/4)",
    packagePrice: 15000,
    paidAmount: 15000,
    balanceDue: 0,
    totalHours: 6,
    usedHours: 0,
    remainingHours: 6,
    status: "Active",
    timestamp: "2026-09-26 18:00"
  });

  // 2. Menuka Wijebandara (Package: Hourly Flex (2h @ Rs. 3,000). Prev paid 7000, today 3.5h @ 4500 unpaid. Total fee = Rs. 15,500, Balance due = Rs. 8,500)
  upsertCustomerRow(sheet, {
    id: "u-menuka",
    name: "Menuka Wijebandara",
    email: "menuka.wijebandara@gmail.com",
    phone: "0771234567",
    packageName: "Hourly Flex (2h @ Rs. 3,000)",
    packagePrice: 15500,
    paidAmount: 7000,
    balanceDue: 8500,
    totalHours: 11.5,
    usedHours: 6.5,
    remainingHours: 5.0,
    status: "Active",
    timestamp: "2026-10-05 15:52"
  });

  // 3. Janith Mihira (One-time recording session: Rs. 2,000 to collect)
  upsertCustomerRow(sheet, {
    id: "u-janith",
    name: "Janith Mihira",
    email: "janith.mihira@gmail.com",
    phone: "0712345678",
    packageName: "One-Time Recording Session",
    packagePrice: 2000,
    paidAmount: 0,
    balanceDue: 2000,
    totalHours: 2,
    usedHours: 1,
    remainingHours: 1,
    status: "Active",
    timestamp: "2026-09-29 14:00"
  });

  // Populate verified bank payments into Side Table 2
  const realPayments = [
    ["2026-09-26", "Kavindya Kodithuwakku", 15000, "PB-KAV-15000", "People's Bank Godakawela", "Verified"],
    ["2026-09-21", "Menuka Wijebandara", 7000, "PB-MEN-7000", "People's Bank Godakawela", "Verified"]
  ];
  sheet.getRange("O19:T20").setValues(realPayments)
    .setBackground("#12141F").setFontColor("#F8FAFC").setFontSize(9);
  sheet.getRange("Q19:Q20").setNumberFormat("[$Rs. ]#,##0.00").setFontColor("#34D399").setFontWeight("bold");

  recalculateFinancials();
  SpreadsheetApp.getActiveSpreadsheet().toast("✓ Real Customer Data Loaded: Kavindya, Menuka & Janith!", "Think Studio", 5);
}

/**
 * Specifically update Menuka Wijebandara with Today's 3.5h Session (Rs. 4,500 Unpaid)
 * Directly updates Row 5 in Google Sheet!
 */
function updateMenukaTodaySession() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME) || setupThinkStudioDashboard();

  upsertCustomerRow(sheet, {
    id: "u-menuka",
    name: "Menuka Wijebandara",
    email: "menuka.wijebandara@gmail.com",
    phone: "0771234567",
    packageName: "Hourly Flex (2h @ Rs. 3,000)",
    packagePrice: 15500,
    paidAmount: 7000,
    balanceDue: 8500,
    totalHours: 11.5,
    usedHours: 6.5,
    remainingHours: 5.0,
    status: "Active",
    timestamp: Utilities.formatDate(new Date(), "Asia/Colombo", "yyyy-MM-dd HH:mm")
  });

  recalculateFinancials();
  SpreadsheetApp.getActiveSpreadsheet().toast("✓ Menuka Wijebandara Updated: Today 3.5h added! Balance Due: Rs. 8,500", "Think Studio", 5);
}
