<html>
<head>
<title>PrintFormatter.py</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
.s0 { color: #5c6370;}
.s1 { color: #bbbbbb;}
.s2 { color: #d55fde;}
.s3 { color: #89ca78;}
.s4 { color: #2bbac5;}
</style>
</head>
<body bgcolor="#282c34">
<table CELLSPACING=0 CELLPADDING=5 COLS=1 WIDTH="100%" BGCOLOR="#606060" >
<tr><td><center>
<font face="Arial, Helvetica" color="#000000">
PrintFormatter.py</font>
</center></td></tr></table>
<pre><span class="s0"># i want colored shell text to help differentiate the types of inputs and outputs for users, instead of</span>
<span class="s0"># defining the color every time, this file will be for pre-defining the inputs and handling them.</span>

<span class="s2">def </span><span class="s1">errorPrint(text):</span>
    <span class="s1">print(</span><span class="s3">'</span><span class="s4">\033</span><span class="s3">[93m' </span><span class="s1">+text)</span>

<span class="s2">def </span><span class="s1">Blue_Output(text):</span>
    <span class="s1">print(</span><span class="s3">'</span><span class="s4">\033</span><span class="s3">[94m'</span><span class="s1">+ text)</span>


<span class="s2">def </span><span class="s1">Green_Output(text):</span>
    <span class="s1">print(</span><span class="s3">'</span><span class="s4">\033</span><span class="s3">[92m' </span><span class="s1">+ text)</span>


<span class="s2">def </span><span class="s1">CInput(text):</span>
    <span class="s1">inputed_text = input(</span><span class="s3">'</span><span class="s4">\033</span><span class="s3">[95m' </span><span class="s1">+ text)</span>
    <span class="s1">str(inputed_text)</span>
    <span class="s2">return </span><span class="s1">inputed_text</span></pre>
</body>
</html>