;; Module to create a Polarion Requirement and link it to a TestCase

(import [polarion-testng.core [TestNGToPolarion]]
        [polarion-testng.utils [*]]
        [re]
        [pyrsistent [m v s pvector PRecord field]]
        [pylarion.work_item [Requirement]])

(defn requirement-exists?
  [title]
  (let [q (title-query title)
        reqs (query-requirement q)
        fltr (fn [r]
               (print "Checking" (unicode r.title))
               (= title (unicode r.title)))]
    (first (filter fltr reqs))))


(defn create-requirement
  [project-id title &optional [description ""]
                              [reqtype "functional"]
   [severity "should_have"]]
  ;; check to see if this Requirement exists already
  (let [existing (requirement-exists? title)]
    (if existing
      exiting
      (.create Requirement project-id title description :severity severity :reqtype reqtype))))
(setv create-requirement.__doc__
      "Creates a new Requirement in Polarion.  Must supply a project id the REquirement belongs to
and a title for the Requirement.  Optionally a description can be provided, and the requirement
type defaults to functional, and the severity as should_have")



