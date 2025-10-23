<html>
<head>
<title>Externals_test.py</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
.s0 { color: #5c6370;}
.s1 { color: #bbbbbb;}
.s2 { color: #d55fde;}
.s3 { color: #89ca78;}
.s4 { color: #d19a66;}
.s5 { color: #2bbac5;}
</style>
</head>
<body bgcolor="#282c34">
<table CELLSPACING=0 CELLPADDING=5 COLS=1 WIDTH="100%" BGCOLOR="#606060" >
<tr><td><center>
<font face="Arial, Helvetica" color="#000000">
Externals_test.py</font>
</center></td></tr></table>
<pre><span class="s0"># Externals_test.py</span>
<span class="s2">import </span><span class="s1">os, stat, shutil, unittest</span>
<span class="s2">from </span><span class="s1">external_runner </span><span class="s2">import </span><span class="s1">run_external, resolve_executable, NOT_EXEC, NOT_FOUND</span>

<span class="s2">class </span><span class="s1">TestExternals(unittest.TestCase):</span>
    <span class="s2">def </span><span class="s1">test_path_lookup(self):</span>
        <span class="s1">self.assertIsNotNone(resolve_executable(</span><span class="s3">&quot;ls&quot;</span><span class="s1">))</span>

    <span class="s2">def </span><span class="s1">test_absolute_path_exec(self):</span>
        <span class="s1">path = shutil.which(</span><span class="s3">&quot;ls&quot;</span><span class="s1">) </span><span class="s2">or </span><span class="s3">&quot;/bin/ls&quot;</span>
        <span class="s1">code, out, err = run_external([path], capture=</span><span class="s2">True</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(code, </span><span class="s4">0</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(err, </span><span class="s3">&quot;&quot;</span><span class="s1">)</span>

    <span class="s2">def </span><span class="s1">test_argv_quoting(self):</span>
        <span class="s1">code, out, err = run_external([</span><span class="s3">&quot;/bin/echo&quot;</span><span class="s1">, </span><span class="s3">&quot;a b&quot;</span><span class="s1">], capture=</span><span class="s2">True</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(code, </span><span class="s4">0</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(out, </span><span class="s3">&quot;a b</span><span class="s5">\n</span><span class="s3">&quot;</span><span class="s1">)</span>

    <span class="s2">def </span><span class="s1">test_stderr_visible(self):</span>
        <span class="s1">code, out, err = run_external([</span><span class="s3">&quot;ls&quot;</span><span class="s1">, </span><span class="s3">&quot;/definitely-not-real-xyz&quot;</span><span class="s1">], capture=</span><span class="s2">True</span><span class="s1">)</span>
        <span class="s1">self.assertNotEqual(code, </span><span class="s4">0</span><span class="s1">)</span>
        <span class="s1">self.assertTrue(err.strip() != </span><span class="s3">&quot;&quot;</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(out, </span><span class="s3">&quot;&quot;</span><span class="s1">)</span>

    <span class="s2">def </span><span class="s1">test_not_found_127(self):</span>
        <span class="s1">code, _, _ = run_external([</span><span class="s3">&quot;__no_such_cmd__&quot;</span><span class="s1">], capture=</span><span class="s2">True</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(code, NOT_FOUND)</span>

    <span class="s2">def </span><span class="s1">test_permission_126_or_127(self):</span>
        <span class="s1">fname = </span><span class="s3">&quot;noexec.sh&quot;</span>
        <span class="s2">with </span><span class="s1">open(fname, </span><span class="s3">&quot;w&quot;</span><span class="s1">) </span><span class="s2">as </span><span class="s1">f:</span>
            <span class="s1">f.write(</span><span class="s3">&quot;#!/bin/sh</span><span class="s5">\n</span><span class="s3">echo hi</span><span class="s5">\n</span><span class="s3">&quot;</span><span class="s1">)</span>
        <span class="s2">try</span><span class="s1">:</span>
            <span class="s1">os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR)  </span>
            <span class="s1">code, _, _ = run_external([</span><span class="s3">f&quot;./</span><span class="s5">{</span><span class="s1">fname</span><span class="s5">}</span><span class="s3">&quot;</span><span class="s1">], capture=</span><span class="s2">True</span><span class="s1">)</span>
            <span class="s1">self.assertIn(code, (NOT_EXEC, NOT_FOUND))  </span>
        <span class="s2">finally</span><span class="s1">:</span>
            <span class="s1">os.remove(fname)</span>

    <span class="s2">def </span><span class="s1">test_shebang_exec(self):</span>
        <span class="s1">fname = </span><span class="s3">&quot;hello.sh&quot;</span>
        <span class="s2">with </span><span class="s1">open(fname, </span><span class="s3">&quot;w&quot;</span><span class="s1">) </span><span class="s2">as </span><span class="s1">f:</span>
            <span class="s1">f.write(</span><span class="s3">&quot;#!/bin/sh</span><span class="s5">\n</span><span class="s3">echo hello</span><span class="s5">\n</span><span class="s3">&quot;</span><span class="s1">)</span>
        <span class="s2">try</span><span class="s1">:</span>
            <span class="s1">os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR) </span>
            <span class="s1">code, out, err = run_external([</span><span class="s3">f&quot;./</span><span class="s5">{</span><span class="s1">fname</span><span class="s5">}</span><span class="s3">&quot;</span><span class="s1">], capture=</span><span class="s2">True</span><span class="s1">)</span>
            <span class="s1">self.assertEqual(code, </span><span class="s4">0</span><span class="s1">)</span>
            <span class="s1">self.assertEqual(out, </span><span class="s3">&quot;hello</span><span class="s5">\n</span><span class="s3">&quot;</span><span class="s1">)</span>
            <span class="s1">self.assertEqual(err, </span><span class="s3">&quot;&quot;</span><span class="s1">)</span>
        <span class="s2">finally</span><span class="s1">:</span>
            <span class="s1">os.remove(fname)</span>

    <span class="s2">def </span><span class="s1">test_large_output_no_deadlock(self):</span>
        <span class="s1">py = </span><span class="s3">&quot;import sys; sys.stdout.write('x'*50000)</span><span class="s5">\n</span><span class="s3">&quot;</span>
        <span class="s1">code, out, err = run_external([</span><span class="s3">&quot;python3&quot;</span><span class="s1">, </span><span class="s3">&quot;-c&quot;</span><span class="s1">, py], capture=</span><span class="s2">True</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(code, </span><span class="s4">0</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(len(out), </span><span class="s4">50000</span><span class="s1">)</span>
        <span class="s1">self.assertEqual(err, </span><span class="s3">&quot;&quot;</span><span class="s1">)</span>

<span class="s2">if </span><span class="s1">__name__ == </span><span class="s3">&quot;__main__&quot;</span><span class="s1">:</span>
    <span class="s1">unittest.main(verbosity=</span><span class="s4">2</span><span class="s1">)</span>
</pre>
</body>
</html>