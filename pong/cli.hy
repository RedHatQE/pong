(import [argparse [ArgumentParser]]
        [pong.utils [*]]
        [pong.logger [log]]
        [shutil])

;; If we ever get to python3 support
(try
 (import [configparser])
 (except [e ImportError]
   (import [ConfigParser :as configparser])))

;; FIXME: Ok, this is huge.  Let's also create a config file (YAML?) and the CLI can override
;; anything in the config file
(defn gen-argparse
  []
  (let [parser (ArgumentParser)]
    (.add-argument parser "--query-testcase" :help "List test cases only")
    (.add_argument parser "--get-default-project-id" :help "Display the .pylarion project then quit"
                   :action "store_true" :default False)
    (.add_argument parser "--set-project-id" :help "Set project id"
                   :choices ["RedHatEnterpriseLinux7" "RHEL6"])
    (.add_argument parser "--user" :help "Set the .pylarion user")
    (.add_argument parser "--password" :help "Set the .pylarion user's password")
    (.add_argument parser "--get-latest-testrun" :help "Find the latest testrun id"
                                                 :action "store_true" :default False)
    (.add_argument parser "-r" "--result-path" :help "path to testng-result.xml")
    (.add_argument parser "-p" "--project-id" :help "project id (defaults to what is in .pylarion")
    (.add_argument parser "-i" "--testrun-id" :help "Base name of the testrun")
    (.add_argument parser "-t" "--template-id" :help "Name of TestRun Template to get tests from"
                                               :required True)
    (.add_argument parser "-g" "--generate-only" :help "Only autogenerate or update testcases"
                                                 :action "store_true" :default False)
    (.add_argument parser "-u" "--update-run" :help "If specified with an existing TestRun ID
                                                     update the existing TestRun.  If ID does not 
                                                     exist, use it to create new TestRun ID 
                                                     (this will override -t)")
    (.add_argument parser "--testrun-prefix" :help "A str prefix to be added before an auto generation
                                                   Polarion TestRun id.  (defaults to 'RHSM')")
    (.add_argument parser "--testrun-suffix" :help "A str suffix to be added before an auto generation
                                                   Polarion TestRun id.  (defaults to 'RHSM')")
    (.add_argument parser "--req-prefix" :help "A str prefix to be added to an auto generated Polarion
                                               Requirement title (defaults to empty string)")
    (.add_argument parser "--distro" :help "The linux distro tested (defaults to RHEL)"
                   :default "RHEL")
    (.add_argument parser "--distro-major" :help "The major version of the distro")
    (.add_argument parser "--distro-minor" :help "The minor version (if any) of the distro")
    (.add_argument parser "-a" "--arch" :help "The machine arch being tested (defaults to x86_64)"
                   :default "x86_64")
    (.add_argument parser "-V" "--variant" :help "The variant of distro (eg Server, Client)"
                   :default "Server")
    (.add_argument parser "-P" "--pylarion-path" :help "path to .pylarion file (defaults to ~/.pylarion")
    (.add_argument parser "-b" "--base-queries" :help "a sequence of strings to be used as queries"
                   :nargs "*")
    (.add_argument parser "-e" "--environment-file" :help "Path to the ${TEST_ENVIRONMENT}")
    parser))


(defn only-pretty-polarion
  [obj field]
  (let [result False]
    (try
     (let [no-under (.startswith field "_")
           attrib (getattr obj field)]
       (setv result (and no-under (and attrib
                                       (not (callable attrib))))))
     (except [ae AttributeError]
       (setv result  False))
     (except [te TypeError]
       (setv result  False)))
    result))

(defn print-kv
  [obj field]
  (print field "=" (getattr obj field)))


(defn query-testcase
  [query]
  (for [test (query-test-case query)]
    (let [msg (+ test.work_item_id " " test.title)]
      (.info log msg))))


(defn get-default-projectid
  [orig]
  (.info log (get-default-project)))


(defn get-latest-testrun
  [testrun-id]
  (let [tr (get-latest-test-run testrun-id)
        valid (.partial toolz only-pretty-polarion tr)
        fields (filter valid (dir tr))]
    (for [attr fields]
      (print-kv tr attr))))


;; Creates a parser to edit the .pylarion file 
(defn create-cfg-parser
  [&optional path]
  (let [cpath (if (is path None)
                (.expanduser os.path "~/.pylarion")
                path)
        cparser (configparser.ConfigParser)]
    (if (not (.exists os.path cpath))
      (raise (Exception (.format "{} does not exist" cpath)))
      (with [fp (open cpath)]
            (let [cfg (.readfp cparser fp)]
              cparser)))))


(defn create-backup
  [orig &optional backup]
  (let [backup-path (if backup
                      backup
                      (+ orig ".bak"))]
    (.copy shutil orig backup-path)))
(setv create-backup.__doc__
      (+ "creates a backup copy of original.  f backup is given, it must be the full name" 
         " otherwise if backup is not given, the original file name will be appended with .bak"))


(defn set-project-id
  [dot-pylarion project-id &optional backup-path]
  (create-backup dot-pylarion)
  (let [cparser (create-cfg-parser :path dot-pylarion)]
    (with [newpy (open dot-pylarion "w")]
          (.set cparser "webservice" "default_project" project-id)
          (.write cparser newpy))))
(setv set-project-id.__doc__
      r"Sets the .pylarion file to the new project id and creates a backup of the original")
